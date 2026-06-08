"""Kubernetes deployment utilities for TML platform."""

import yaml
from typing import Dict, Any, List
from pathlib import Path

from tml.core.config import config


class KubernetesDeploymentGenerator:
    """Generate Kubernetes deployment manifests for TML platform."""

    def __init__(self, namespace: str = "tml-platform"):
        self.namespace = namespace
        self.manifests_dir = Path("orchestration/k8s")
        self.manifests_dir.mkdir(parents=True, exist_ok=True)

    def generate_namespace(self) -> Dict[str, Any]:
        """Generate namespace manifest."""
        return {
            "apiVersion": "v1",
            "kind": "Namespace",
            "metadata": {"name": self.namespace, "labels": {"app": "tml-platform"}},
        }

    def generate_api_server_deployment(self) -> Dict[str, Any]:
        """Generate API server deployment."""
        return {
            "apiVersion": "apps/v1",
            "kind": "Deployment",
            "metadata": {
                "name": "tml-api-server",
                "namespace": self.namespace,
                "labels": {"app": "tml-api-server", "component": "api"},
            },
            "spec": {
                "replicas": config.serving.num_replicas,
                "selector": {"matchLabels": {"app": "tml-api-server"}},
                "template": {
                    "metadata": {"labels": {"app": "tml-api-server"}},
                    "spec": {
                        "containers": [
                            {
                                "name": "api-server",
                                "image": "tml-platform:latest",
                                "ports": [{"containerPort": 8000, "name": "http"}],
                                "env": [
                                    {"name": "TML_ENVIRONMENT", "value": "production"},
                                    {"name": "REDIS_HOST", "value": "tml-redis"},
                                    {
                                        "name": "KAFKA_BOOTSTRAP_SERVERS",
                                        "value": "tml-kafka:9092",
                                    },
                                    {
                                        "name": "CASSANDRA_HOSTS",
                                        "value": "tml-cassandra",
                                    },
                                    {
                                        "name": "MLFLOW_TRACKING_URI",
                                        "value": "http://tml-mlflow:5000",
                                    },
                                ],
                                "resources": {
                                    "requests": {"memory": "512Mi", "cpu": "250m"},
                                    "limits": {"memory": "1Gi", "cpu": "500m"},
                                },
                                "livenessProbe": {
                                    "httpGet": {"path": "/health", "port": 8000},
                                    "initialDelaySeconds": 30,
                                    "periodSeconds": 10,
                                },
                                "readinessProbe": {
                                    "httpGet": {"path": "/health", "port": 8000},
                                    "initialDelaySeconds": 5,
                                    "periodSeconds": 5,
                                },
                            }
                        ]
                    },
                },
            },
        }

    def generate_api_server_service(self) -> Dict[str, Any]:
        """Generate API server service."""
        return {
            "apiVersion": "v1",
            "kind": "Service",
            "metadata": {
                "name": "tml-api-server",
                "namespace": self.namespace,
                "labels": {"app": "tml-api-server"},
            },
            "spec": {
                "selector": {"app": "tml-api-server"},
                "ports": [{"port": 80, "targetPort": 8000, "name": "http"}],
                "type": "LoadBalancer",
            },
        }

    def generate_kafka_processor_deployment(self) -> Dict[str, Any]:
        """Generate Kafka processor deployment."""
        return {
            "apiVersion": "apps/v1",
            "kind": "Deployment",
            "metadata": {
                "name": "tml-kafka-processor",
                "namespace": self.namespace,
                "labels": {"app": "tml-kafka-processor", "component": "processor"},
            },
            "spec": {
                "replicas": 2,
                "selector": {"matchLabels": {"app": "tml-kafka-processor"}},
                "template": {
                    "metadata": {"labels": {"app": "tml-kafka-processor"}},
                    "spec": {
                        "containers": [
                            {
                                "name": "kafka-processor",
                                "image": "tml-platform:latest",
                                "command": [
                                    "python",
                                    "-m",
                                    "tml.ingestion.kafka_consumer",
                                ],
                                "env": [
                                    {"name": "TML_ENVIRONMENT", "value": "production"},
                                    {
                                        "name": "KAFKA_BOOTSTRAP_SERVERS",
                                        "value": "tml-kafka:9092",
                                    },
                                    {"name": "REDIS_HOST", "value": "tml-redis"},
                                    {
                                        "name": "CASSANDRA_HOSTS",
                                        "value": "tml-cassandra",
                                    },
                                ],
                                "resources": {
                                    "requests": {"memory": "1Gi", "cpu": "500m"},
                                    "limits": {"memory": "2Gi", "cpu": "1000m"},
                                },
                            }
                        ]
                    },
                },
            },
        }

    def generate_redis_deployment(self) -> Dict[str, Any]:
        """Generate Redis deployment."""
        return {
            "apiVersion": "apps/v1",
            "kind": "Deployment",
            "metadata": {
                "name": "tml-redis",
                "namespace": self.namespace,
                "labels": {"app": "tml-redis", "component": "cache"},
            },
            "spec": {
                "replicas": 1,
                "selector": {"matchLabels": {"app": "tml-redis"}},
                "template": {
                    "metadata": {"labels": {"app": "tml-redis"}},
                    "spec": {
                        "containers": [
                            {
                                "name": "redis",
                                "image": "redis:7-alpine",
                                "ports": [{"containerPort": 6379, "name": "redis"}],
                                "resources": {
                                    "requests": {"memory": "256Mi", "cpu": "100m"},
                                    "limits": {"memory": "512Mi", "cpu": "200m"},
                                },
                                "volumeMounts": [
                                    {"name": "redis-data", "mountPath": "/data"}
                                ],
                            }
                        ],
                        "volumes": [
                            {
                                "name": "redis-data",
                                "persistentVolumeClaim": {"claimName": "redis-pvc"},
                            }
                        ],
                    },
                },
            },
        }

    def generate_redis_service(self) -> Dict[str, Any]:
        """Generate Redis service."""
        return {
            "apiVersion": "v1",
            "kind": "Service",
            "metadata": {
                "name": "tml-redis",
                "namespace": self.namespace,
                "labels": {"app": "tml-redis"},
            },
            "spec": {
                "selector": {"app": "tml-redis"},
                "ports": [{"port": 6379, "targetPort": 6379, "name": "redis"}],
                "type": "ClusterIP",
            },
        }

    def generate_persistent_volume_claims(self) -> List[Dict[str, Any]]:
        """Generate persistent volume claims."""
        pvcs = []

        # Redis PVC
        pvcs.append(
            {
                "apiVersion": "v1",
                "kind": "PersistentVolumeClaim",
                "metadata": {"name": "redis-pvc", "namespace": self.namespace},
                "spec": {
                    "accessModes": ["ReadWriteOnce"],
                    "resources": {"requests": {"storage": "10Gi"}},
                },
            }
        )

        # Cassandra PVC
        pvcs.append(
            {
                "apiVersion": "v1",
                "kind": "PersistentVolumeClaim",
                "metadata": {"name": "cassandra-pvc", "namespace": self.namespace},
                "spec": {
                    "accessModes": ["ReadWriteOnce"],
                    "resources": {"requests": {"storage": "50Gi"}},
                },
            }
        )

        return pvcs

    def generate_configmap(self) -> Dict[str, Any]:
        """Generate ConfigMap for TML configuration."""
        return {
            "apiVersion": "v1",
            "kind": "ConfigMap",
            "metadata": {"name": "tml-config", "namespace": self.namespace},
            "data": {
                "TML_ENVIRONMENT": "production",
                "TML_LOG_LEVEL": "INFO",
                "MODEL_BASE_TYPE": "river",
                "MODEL_MAX_IN_MEMORY": "10000",
                "MODEL_DRIFT_THRESHOLD": "0.1",
                "SERVING_NUM_REPLICAS": "4",
                "MONITORING_DRIFT_CHECK_INTERVAL": "300",
            },
        }

    def generate_all_manifests(self) -> Dict[str, Dict[str, Any]]:
        """Generate all Kubernetes manifests."""
        manifests = {
            "namespace": self.generate_namespace(),
            "configmap": self.generate_configmap(),
            "api-deployment": self.generate_api_server_deployment(),
            "api-service": self.generate_api_server_service(),
            "kafka-processor": self.generate_kafka_processor_deployment(),
            "redis-deployment": self.generate_redis_deployment(),
            "redis-service": self.generate_redis_service(),
        }

        # Add PVCs
        pvcs = self.generate_persistent_volume_claims()
        for i, pvc in enumerate(pvcs):
            manifests[f"pvc-{i}"] = pvc

        return manifests

    def save_manifests(self):
        """Save all manifests to files."""
        manifests = self.generate_all_manifests()

        for name, manifest in manifests.items():
            file_path = self.manifests_dir / f"{name}.yaml"
            with open(file_path, "w") as f:
                yaml.dump(manifest, f, default_flow_style=False)

        print(f"Kubernetes manifests saved to {self.manifests_dir}")


if __name__ == "__main__":
    generator = KubernetesDeploymentGenerator()
    generator.save_manifests()
