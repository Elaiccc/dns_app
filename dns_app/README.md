# Lab 3 DNS application

Author: Ziyi Liu (zl6722)

US resolves the Fibonacci server through AS over UDP, requests the value from FS over HTTP, and returns it to the client. All services use Python's standard library; no pip packages are required.

| Service | Default port | Role |
| --- | --- | --- |
| US | 8080/TCP | HTTP entry point |
| FS | 9090/TCP | Registration and Fibonacci calculation |
| AS | 53533/UDP | Persistent authoritative records |

## Run with Docker

From this `dns_app` directory, with Docker Compose installed:

```sh
docker compose up --build -d
docker compose exec -T fs python - < register_compose.py
curl -i 'http://localhost:8080/fibonacci?hostname=fibonacci.com&fs_port=9090&number=10&as_ip=as&as_port=53533'
```

Expected: registration returns `201 Registered`; the GET returns HTTP 200 with body `55`. Inside Docker, US reaches AS by the Compose service name `as`, and AS returns FS's container IPv4 address. Re-run registration after recreating the FS container because its address may change.

```sh
curl -i 'http://localhost:9090/fibonacci?number=10'
curl -i 'http://localhost:9090/fibonacci?number=abc'
curl -i 'http://localhost:8080/fibonacci?number=10'
docker compose logs
docker compose down
```

The three checks should return 200, 400, and 400. AS records survive `docker compose down` in the named volume. `docker compose down -v` deliberately deletes that volume.

## Run without Docker

Use Python 3.12 or later. Open three terminals in `dns_app` and run one command in each:

```sh
python3 AS/server.py
python3 FS/server.py
python3 US/server.py
```

In a fourth terminal:

```sh
curl -i -X PUT http://localhost:9090/register \
  -H 'Content-Type: application/json' \
  -d '{"hostname":"fibonacci.com","ip":"127.0.0.1","as_ip":"127.0.0.1","as_port":"53533"}'
curl -i 'http://localhost:8080/fibonacci?hostname=fibonacci.com&fs_port=9090&number=10&as_ip=127.0.0.1&as_port=53533'
```

Stop each server with Ctrl+C. AS stores `records.sqlite3` in its working directory. `HOST`, `PORT`, and AS's `DB_PATH` environment variables can override defaults.

## Protocol and behavior

Registration datagram (each line ends with a newline):

```text
TYPE=A
NAME=fibonacci.com VALUE=127.0.0.1 TTL=10
```

AS commits the record to SQLite before acknowledging with `STATUS=OK\n`. FS then returns HTTP 201. This acknowledgment is an implementation choice because the lab does not prescribe one.

Query:

```text
TYPE=A
NAME=fibonacci.com
```

Response:

```text
TYPE=A
NAME=fibonacci.com VALUE=127.0.0.1 TTL=10
```

- Fibonacci uses F(0) = 0 and F(1) = 1. Negative, fractional, empty, or nonnumeric inputs return 400.
- US requires all five parameters. Missing, empty, repeated, or invalid required parameters return 400.
- `as_port` is honored, including the cloud NodePort 30001.
- AS supports IPv4 A records. Re-registration replaces an existing record. TTL is a cache lifetime, not deletion of the authoritative record. US queries AS for each request.
- Unknown records return `ERROR=NOT_FOUND\n` and US returns 404. Malformed UDP requests return `ERROR=BAD_REQUEST\n`. Upstream failures return 502; timeouts return 504.
- This is the lab's simplified text protocol, not standard binary DNS.

## Tests

```sh
python3 test_integration.py
```

The tests start actual AS, FS, and US processes on temporary loopback ports. They check registration, exact UDP responses, direct and end-to-end Fibonacci values, missing parameters, invalid input, unknown names, persistence across an AS restart, and timeouts. See `TEST_RESULTS.txt` for the completed local run.

Docker images and Kubernetes were not run in the preparation environment because Docker and kubectl were unavailable. `deploy_dns.yml` was checked structurally, but no cloud execution is claimed.

## Cloud Kubernetes extra credit

Use a configured cloud cluster with a default StorageClass and nodes that allow the specified NodePorts. In `deploy_dns.yml`, replace every `YOUR_REGISTRY` with your image registry/account. Build for your cluster's architecture and push all three images:

```sh
docker build -t YOUR_REGISTRY/dcn-as:lab3 AS
docker build -t YOUR_REGISTRY/dcn-fs:lab3 FS
docker build -t YOUR_REGISTRY/dcn-us:lab3 US
docker push YOUR_REGISTRY/dcn-as:lab3
docker push YOUR_REGISTRY/dcn-fs:lab3
docker push YOUR_REGISTRY/dcn-us:lab3
kubectl apply -f deploy_dns.yml
kubectl rollout status deployment/dns-as
kubectl rollout status deployment/dns-fs
kubectl rollout status deployment/dns-us
kubectl get pods,services,pvc -o wide
```

The single manifest defines three Deployments, three NodePort Services, and persistent AS storage. Images must be readable by the cluster; private registries also require an image pull secret. If the cluster has no default StorageClass, set the PVC's `storageClassName` to one it provides.

| Service | NodePort | Target port |
| --- | --- | --- |
| AS | 30001/UDP | 53533/UDP |
| FS | 30002/TCP | 9090/TCP |
| US | 30003/TCP | 8080/TCP |

Register the FS Service's stable IPv4 address. The following commands use the default namespace:

```sh
FS_IP=$(kubectl get service dns-fs -o jsonpath='{.spec.clusterIP}')
kubectl exec deployment/dns-fs -- python -c \
  'import http.client,json,sys; c=http.client.HTTPConnection("localhost",9090); c.request("PUT","/register",json.dumps({"hostname":"fibonacci.com","ip":sys.argv[1],"as_ip":"dns-as","as_port":53533}),{"Content-Type":"application/json"}); r=c.getresponse(); print(r.status,r.read().decode())' "$FS_IP"
```

Replace `NODE_IP` below with a reachable worker-node address. With node access allowed, this exercises both the US and AS NodePorts; US calls FS internally through its registered Service IP:

```sh
curl -i 'http://NODE_IP:30003/fibonacci?hostname=fibonacci.com&fs_port=9090&number=10&as_ip=NODE_IP&as_port=30001'
curl -i 'http://NODE_IP:30002/fibonacci?number=10'
```

If your provider blocks pod-to-node NodePort traffic, use `as_ip=dns-as&as_port=53533` for the internal AS lookup, and verify 30001/UDP separately from a reachable machine. Keep the successful cloud output or screenshots for extra-credit evidence. This live cloud step still needs to be performed.

Reference: https://kubernetes.io/docs/concepts/services-networking/service/

## Submission

1. Review the Word report and sign its independent-effort statement if appropriate.
2. Copy this entire `dns_app` folder into your own GitHub repository. From that repository's root:

```sh
git add dns_app
git commit -m "Complete Lab 3 DNS application"
git push
```

3. Verify the files and latest commit on GitHub. The lab uses that commit time for grading; no remote commit has been made for you.
4. Upload `DCN-ziyi_liu_lab_3.docx` and `DCN-ziyi_liu_lab_3.zip` to Brightspace before class on October 1, 2026. The ZIP must contain the `dns_app` folder.

`http_evidence/` contains the five instructor-permitted textbook traces and the exact HTTP extracts used in the Word report. These captures are textbook examples, not captures from the student's computer.
