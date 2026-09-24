# Deploying services on Kubernetes

## Pods and deployments

A pod is the smallest deployable unit in Kubernetes and wraps one or more
containers. A deployment manages a replica set of identical pods and rolls out
new container images without downtime.

## Autoscaling

The horizontal pod autoscaler adds or removes pod replicas based on CPU usage
or custom metrics, so the cluster scales with traffic.
