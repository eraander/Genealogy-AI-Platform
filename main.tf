terraform {
    required_providers {
        kubernetes = {
            source = "hashicorp/kubernetes"
            version = "2.23.0"
        }
    }
}

provider "kubernetes" {
    config_path = "~/.kube/config"
}

resource "kubernetes_namespace" "genealogy" {
    metadata {
        name = "genealogy"
    }
}

resource "kubernetes_persistent_volume_claim" "faiss_storage" {
    metadata {
        name = "faiss-storage"
        namespace = kubernetes_namespace.genealogy.metadata[0].name
    }
    spec {
        access_modes = ["ReadWriteOnce"]
        resources {
            requests = {
                storage = "1Gi"
            }
        }
    }
}

resource "kubernetes_deployment" "genealogy_api" {
    metadata {
        name = "genealogy-api"
        namespace = kubernetes_namespace.genealogy.metadata[0].name
    }
    spec {
        replicas = 1
        selector {
            match_labels = {
                app = "genealogy-api"
            }
        }
        template {
            metadata {
                labels = {
                    app = "genealogy-api"
                }
            }
            spec {
                container {
                    name = "genealogy-api"
                    image = "genealogy-api:v1.4"
                    image_pull_policy = "IfNotPresent"
                    port {
                        container_port = 8000
                    }
                    env {
                        name  = "PYTHONPATH"
                        value = "/"
                    }
                    env {
                        name  = "OPENAI_API_KEY"
                        value = var.openai_api_key
                    }
                    env {
                        name  = "ANTHROPIC_API_KEY"
                        value = var.anthropic_api_key
                    }
                    env {
                        name  = "LANGFUSE_PUBLIC_KEY"
                        value = var.langfuse_public_key
                    }
                    env {
                        name  = "LANGFUSE_SECRET_KEY"
                        value = var.langfuse_secret_key
                    }
                    env {
                        name  = "LANGFUSE_HOST"
                        value = var.langfuse_host
                    }
                    env {
                        name  = "LANGFUSE_BASE_URL"
                        value = var.langfuse_base_url
                    }
                    env {
                        name  = "REDIS_URL"
                        value = "redis://localhost:6379"
                    }
                    env {
                        name = "REDIS_HOST"
                        value = "localhost"
                    }
                    env {
                        name = "REDIS_PORT"
                        value = "6379"
                    }
                    volume_mount {
                        mount_path = "/app/data/faiss_index"
                        name       = "faiss-volume"
                    }
                }
                container {
                    name  = "redis"
                    image = "redis:alpine"
                    port {
                        container_port = 6379
                    }
                }
                container {
                    name  = "celery-eval-worker"
                    image = "genealogy-api:v1.4"
                    image_pull_policy = "IfNotPresent"
                    
                    command = ["celery", "-A", "app.core.celery_app", "worker", "--loglevel=info", "--concurrency=2"]
                    env {
                        name  = "PYTHONPATH"
                        value = "/"
                    }
                    env {
                        name  = "OPENAI_API_KEY"
                        value = var.openai_api_key
                    }
                    env {
                        name  = "ANTHROPIC_API_KEY"
                        value = var.anthropic_api_key
                    }
                    env {
                        name  = "LANGFUSE_PUBLIC_KEY"
                        value = var.langfuse_public_key
                    }
                    env {
                        name  = "LANGFUSE_SECRET_KEY"
                        value = var.langfuse_secret_key
                    }
                    env {
                        name  = "LANGFUSE_HOST"
                        value = var.langfuse_host
                    }
                    env {
                        name  = "LANGFUSE_BASE_URL"
                        value = var.langfuse_base_url
                    }
                    env {
                        name  = "REDIS_URL"
                        value = "redis://localhost:6379"
                    }
                    env {
                        name = "REDIS_HOST"
                        value = "localhost"
                    }
                    env {
                        name = "REDIS_PORT"
                        value = "6379"
                    }
                    volume_mount {
                        mount_path = "/app/data/faiss_index"
                        name       = "faiss-volume"
                    }

                    resources {
                        requests = {
                            cpu = "250m"
                            memory = "256Mi"
                        }
                        limits = {
                            cpu = "1000m"
                            memory = "1Gi"
                        }
                    }
                    
                }
                volume {
                    name = "faiss-volume"
                    persistent_volume_claim {
                        claim_name = kubernetes_persistent_volume_claim.faiss_storage.metadata[0].name
                    }
                }
            }
        }
    }
}

resource "kubernetes_service" "genealogy_service" {
    metadata {
        name = "genealogy-service"
        namespace = kubernetes_namespace.genealogy.metadata[0].name
    }
    spec {
        selector = {
            app = "genealogy-api"
        }
        port {
            port = 80
            target_port = 8000
            node_port = 30080
        }
        type = "NodePort"
    }
}