# Docker Infrastructure

The root `docker-compose.yml` is the single entry point for the Phase 0 local environment. This directory is reserved for Docker-specific assets that become necessary later; service configuration remains centralized in Compose for now.

Phase 0 provisions PostgreSQL, Redis, and Qdrant without creating domain tables, cache business logic, or vector collections.
