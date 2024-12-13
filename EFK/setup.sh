#!/bin/bash

NAMESPACE="efk"
ELASTICSEARCH_PASSWORD="Leouf31071987."
FLUENTD_PASSWORD="Leouf31071987."
ELASTICSEARCH_URL="http://elasticsearch.efk.svc.cluster.local:9200"
MAX_WAIT_TIME=300  # Maximum wait time in seconds
SLEEP_INTERVAL=5  # Sleep interval in seconds


# Apply Elasticsearch ConfigMap and Deployment
kubectl apply -f elastic.yaml

# Wait for Elasticsearch to be ready
echo "Waiting for Elasticsearch to be ready..."
kubectl wait --for=condition=available --timeout=600s deployment/elasticsearch -n $NAMESPACE


# Set passwords for built-in users
echo "Setting passwords for built-in users..."
kubectl exec -it $(kubectl get pods -n $NAMESPACE -l app=elasticsearch -o jsonpath="{.items[0].metadata.name}") -n $NAMESPACE -- /bin/bash -c "
echo $ELASTICSEARCH_PASSWORD | bin/elasticsearch-setup-passwords auto --batch
"


# Create a role for Fluentd
echo "Creating a role for Fluentd..."
curl -X POST "$ELASTICSEARCH_URL/_security/role/fluentd_writer" -H "Content-Type: application/json" -u elastic:$ELASTICSEARCH_PASSWORD -d'
{
  "cluster": ["manage_index_templates", "monitor", "manage_ilm"],
  "indices": [
    {
      "names": ["fluentd-*"],
      "privileges": ["write", "create_index"]
    }
  ]
}'

# Create a user for Fluentd
echo "Creating a user for Fluentd..."
curl -X POST "$ELASTICSEARCH_URL/_security/user/fluentd" -H "Content-Type: application/json" -u elastic:$ELASTICSEARCH_PASSWORD -d"
{
  \"password\": \"$FLUENTD_PASSWORD\",
  \"roles\": [\"fluentd_writer\"],
  \"full_name\": \"Fluentd User\"
}
"

# Create a secret for Fluentd credentials
kubectl create secret generic fluentd-secret --from-literal=password=$FLUENTD_PASSWORD -n $NAMESPACE --dry-run=client -o yaml | kubectl apply -f -

# Apply Fluentd ConfigMap and DaemonSet
kubectl apply -f fluentd.yaml

# Wait for Fluentd DaemonSet to be ready
echo "Waiting for Fluentd DaemonSet to be ready..."
kubectl rollout status daemonset/fluentd -n $NAMESPACE

echo "Setup complete."
