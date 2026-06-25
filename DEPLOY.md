# Deployment Runbook — Urban Soil Co-Lab

Operational guide for deploying code changes and managing the apps on UB CaaS
(OpenShift, project `urban-soil-co-lab`).

---

## Architecture at a glance

- **5 Streamlit apps** (`dashboard`, `field-entry`, `xrf-tech`, `site-builder`, `etl-manager`)
  all run from **one shared image** (`xrf-tech`), each launched with a different `APP_FILE`.
- **Image** is built by a single BuildConfig named `xrf-tech` from `Git@main`.
- All deployments use the image tag **`:latest`** with **`imagePullPolicy: Always`**
  (so rebuilds actually deploy — do NOT pin to an `@sha256:` digest).
- **Persistent data** lives on the `soil-data` PVC, mounted at `/opt/app-root/src/data`
  on every app and on the sync job. `SOIL_DATA_DIR` env var points apps there.
- **SharePoint** (`Urban Soil Co-Lab` library) is the source of truth; an **hourly
  CronJob** (`sharepoint-sync`) syncs SharePoint <-> the volume.

---

## Deploying an app code change (the standard flow)

```bash
# 1. Commit and push your change
git add <files>
git commit -m "describe the change"
git push

# 2. Confirm it landed on main (the build pulls from main)
git log origin/main -1 --oneline

# 3. Rebuild the shared image (rebuilds for ALL 5 apps)
./oc start-build xrf-tech -n urban-soil-co-lab --wait
#    Wait for "Complete". If it fails: ./oc logs build/xrf-tech-<N> -n urban-soil-co-lab

# 4. Roll out the app(s) that changed (forces a fresh pod to pull :latest)
./oc rollout restart deployment/<app-name> -n urban-soil-co-lab

# 5. Verify a new pod is Running
./oc get pods -n urban-soil-co-lab | grep <app-name>
```

Then hard-refresh the app URL (Cmd/Ctrl+Shift+R) and confirm the change is live.

### If the change touches SHARED code
`paths.py`, `map_renderer.py`, `groundsense_config.py`, `github_sync.py`, etc. are
imported by multiple apps. Restart all five:

```bash
for APP in dashboard etl-manager field-entry site-builder xrf-tech; do
  ./oc rollout restart deployment/$APP -n urban-soil-co-lab
done
```

### Confirm the new code is actually in the pod (optional, when in doubt)
```bash
POD=$(./oc get pods -n urban-soil-co-lab -o name | grep <app-name> | head -1)
./oc exec $POD -- grep -n "something-from-your-change" /opt/app-root/src/src/<file>.py
```

---

## Special cases

### Changed `requirements.txt`
Same flow. Watch the build log — a bad dependency fails at the pip step.
Make sure each requirement is on its OWN line (a missing newline mashes two
together and breaks the build).

### Changed `sync_sharepoint.py`
Rebuild the image (step 3). The CronJob uses `:latest`, so the **next hourly run
picks it up automatically** — no rollout needed. To test immediately:
```bash
./oc create job --from=cronjob/sharepoint-sync sp-test -n urban-soil-co-lab
sleep 25
POD=$(./oc get pods -n urban-soil-co-lab -o name | grep sp-test | head -1)
./oc logs $POD -n urban-soil-co-lab
./oc delete job sp-test -n urban-soil-co-lab
```

### Changed data only (not code)
No build needed — data lives on the volume / in SharePoint, not in the image.

---

## Troubleshooting

### "I rebuilt but the app still shows old code"
1. Did the commit reach main?  `git log origin/main -1 --oneline`
2. Did the build complete?     `./oc get builds -n urban-soil-co-lab | tail`
3. Did a NEW pod start?         `./oc get pods -n urban-soil-co-lab | grep <app>`
   (look for a new suffix + recent age)
4. Is the deployment pinned to a stale digest? It must end in `:latest`:
   ```bash
   ./oc get deployment <app> -n urban-soil-co-lab \
     -o jsonpath='{.spec.template.spec.containers[0].image}{"\n"}'
   ```
   If it shows `@sha256:...`, re-point it to :latest:
   ```bash
   ./oc patch deployment <app> -n urban-soil-co-lab --type=json -p='[
     {"op":"replace","path":"/spec/template/spec/containers/0/image",
      "value":"image-registry.openshift-image-registry.svc:5000/urban-soil-co-lab/xrf-tech:latest"},
     {"op":"add","path":"/spec/template/spec/containers/0/imagePullPolicy","value":"Always"}]'
   ```

### "Unauthorized" on any oc command
Your login token expired. Re-login: OpenShift console -> your name (top right) ->
Copy login command -> Display Token -> paste the `oc login --token=... --server=...`
line (with `./` if using the local oc binary).

### Build fails
```bash
./oc logs build/xrf-tech-<N> -n urban-soil-co-lab | tail -40
```
Read the last lines — usually a pip/requirements error or a Dockerfile step.

---

## SharePoint sync operations

### Check the sync is healthy
```bash
./oc get cronjob sharepoint-sync -n urban-soil-co-lab          # SUSPEND should be False
./oc get jobs -n urban-soil-co-lab | grep sharepoint          # recent jobs: 1/1 = success
```

### See a sync run's output
```bash
POD=$(./oc get pods -n urban-soil-co-lab -o name | grep sharepoint-sync | head -1)
./oc logs $POD -n urban-soil-co-lab
```

### Pause / resume the sync
```bash
./oc patch cronjob sharepoint-sync -n urban-soil-co-lab -p '{"spec":{"suspend":true}}'   # pause
./oc patch cronjob sharepoint-sync -n urban-soil-co-lab -p '{"spec":{"suspend":false}}'  # resume
```

### Check storage usage on the volume
```bash
POD=$(./oc get pods -n urban-soil-co-lab -o name | grep site-builder | head -1)
./oc exec $POD -- du -sh /opt/app-root/src/data /opt/app-root/src/data/.sync_backups
```

---

## Important gotchas (learned the hard way)

- **Quota: CPU is 2/2 (full).** Sync pods schedule only because they're "terminating"
  (pod-level `activeDeadlineSeconds` in the CronJob). Adding another always-on app may
  hit the wall — request a CPU quota bump from UBIT if so.
- **Quota: storage is 1Gi.** PVC expansion needs a UBIT quota increase first, then:
  `./oc patch pvc soil-data -n urban-soil-co-lab -p '{"spec":{"resources":{"requests":{"storage":"5Gi"}}}}'`
- **Never commit the client secret.** It lives only in the `sharepoint-sync` OpenShift
  Secret. The CronJob YAML references it; it does not contain it.
- **Paths are case-sensitive in the container** (`data` != `Data`), unlike macOS.
- **Always `start-build --wait`** so you know the build finished before rolling out.

---

## Secret rotation (when needed)

```bash
./oc delete secret sharepoint-sync -n urban-soil-co-lab
./oc create secret generic sharepoint-sync \
  --from-literal=SP_TENANT_ID='96464a8a-f8ed-40b1-99e2-5f6b50a20250' \
  --from-literal=SP_CLIENT_ID='448531da-6d44-4729-8761-3f518ad44bfa' \
  --from-literal=SP_CLIENT_SECRET='<new-secret>' \
  -n urban-soil-co-lab
```
The next CronJob run uses the new value automatically.

---

## TODO / parked

- [ ] Commit all infra YAML to repo (deployments, services, routes, PVC, cronjob) for reproducibility
- [ ] App authentication (Shibboleth/UBITName) — internal apps currently open
- [ ] SharePoint/Box snapshot backup — pending manager input (frequency, location, retention)
- [ ] CPU quota bump 2 -> 3 (headroom)
- [ ] Health/readiness probes on app deployments