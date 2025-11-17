# Service Endpoints & Connection Guide

## Overview

This document provides URLs, connection strings, and credentials for accessing infrastructure and database services.

For application service ports (both Core Services and Processing Modules), please refer to the single source of truth: the **[Port Allocation Strategy](./Port_allocations.md)** document.

## 🌐 Application Services (Core & Modules)

The ports for all application services are defined in the **[Port Allocation Strategy](./Port_allocations.md)**. Please refer to that document to find the correct development port for each service.

Once you have the port, you can access the following endpoints:

*   **Service Dashboard**: `http://localhost:{port}`
*   **Swagger UI**: `http://localhost:{port}/swagger-ui`
*   **OpenAPI JSON**: `http://localhost:{port}/openapi`
*   **Health Check**: `http://localhost:{port}/health`

---

## 🗄️ Database Connections

### **MySQL (Primary Database)**

| Environment | Host | Port | Database | Username | Password |
|-------------|------|------|----------|----------|----------|
| **Development** | localhost | 3306 | pipeline | pipeline | password |
| **Test** | localhost | 3307 | pipeline_test | pipeline | password |
| **Production** | mysql.company.com | 3306 | pipeline | [vault] | [vault] |

#### **MySQL Connection Strings**

```bash
# Development
mysql -h localhost -P 3306 -u pipeline -ppassword pipeline

# Test
mysql -h localhost -P 3307 -u pipeline -ppassword pipeline_test
```

---

## 🔍 Infrastructure Services

These URLs and ports are for the **development environment** infrastructure, managed by `compose-devservices.yml`.

| Service | URL / Endpoint | Credentials |
| :--- | :--- | :--- |
| **Consul UI** | http://localhost:8500/ui | N/A |
| **OpenSearch API** | http://localhost:9200 | N/A |
| **OpenSearch Dashboards** | http://localhost:5601 | N/A |
| **Kafka Bootstrap** | `localhost:9094` | N/A |
| **Kafka UI** | http://localhost:8889 | N/A |
| **Apicurio Registry API** | http://localhost:8081 | N/A |
| **Apicurio Registry UI** | http://localhost:8888 | N/A |
| **MinIO Console** | http://localhost:9001 | minioadmin/minioadmin |
| **MinIO API** | `http://localhost:9000` | minioadmin/minioadmin |
| **Grafana** | http://localhost:3001 | N/A |

### **Test Environment Infrastructure**

The test environment infrastructure (`compose-test-services.yml`) uses different ports to avoid conflicts. Refer to the **[Port Allocation Strategy](./Port_allocations.md)** for the complete list of test infrastructure ports.

---

## 🐳 Docker & Container Management

### **Docker Compose Services**

```bash
# Start all development infrastructure
docker-compose -f src/test/resources/compose-devservices.yml up -d

# View running containers
docker-compose -f src/test/resources/compose-devservices.yml ps

# View logs for a specific service
docker-compose -f src/test/resources/compose-devservices.yml logs -f consul
```

---

## 🔐 Development Credentials Reference

| Service | URL | Username | Password |
| :--- | :--- | :--- | :--- |
| **MinIO Console** | http://localhost:9001 | `minioadmin` | `minioadmin` |
| **MySQL Database** | localhost:3306 | `pipeline` | `password` |

---

## 🔧 Troubleshooting

### **Common Connection Issues**

| Issue | Solution |
| :--- | :--- |
| **Port already in use** | Use `lsof -i :PORT` to find the conflicting process. For application ports, verify the correct port in the **[Port Allocation Strategy](./Port_allocations.md)**. |
| **Service not registered** | Check the Consul UI (`http://localhost:8500`) and restart the service if needed. |
| **Database connection failed** | Verify the MySQL container is running: `docker ps \| grep mysql`. |
| **Health check failing** | Check service logs and ensure port configurations are aligned with the canonical documentation. |

