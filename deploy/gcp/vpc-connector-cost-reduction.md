# VPC Connector Cost Reduction

If your VPC connector was created with higher `min-instances` or `max-instances` than needed, it will incur higher cost. The recommended settings are `--min-instances=1 --max-instances=3`.

**Note:** GCP does not allow updating instance counts on an existing connector. You must create a new connector and switch Cloud Run to use it, then delete the old one.

## Steps

1. **Create a new connector** with cost-optimized settings:

   ```bash
   gcloud compute networks vpc-access connectors create openproxyai-connector-v2 \
     --region=northamerica-northeast1 \
     --range=10.8.0.16/28 \
     --min-instances=1 \
     --max-instances=3
   ```

   Use a non-overlapping IP range; e.g. `10.8.0.16/28` (the old connector uses `10.8.0.0/28`).

2. **Update Cloud Run** to use the new connector:

   ```bash
   gcloud run services update openproxyai-backend \
     --region=northamerica-northeast1 \
     --vpc-connector=projects/project-ebccbe1a-a432-4e88-887/locations/northamerica-northeast1/connectors/openproxyai-connector-v2
   ```

3. **Update GitHub secret** `GCP_VPC_CONNECTOR` to the new connector path.

4. **Redeploy** so subsequent deployments use the new connector.

5. **Delete the old connector** (after confirming the service works):

   ```bash
   gcloud compute networks vpc-access connectors delete openproxyai-connector \
     --region=northamerica-northeast1
   ```

Expect brief connectivity interruption during the swap (Cloud Run → Redis via old connector stops when you update, then resumes via new connector).
