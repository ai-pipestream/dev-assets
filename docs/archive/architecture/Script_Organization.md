# Script Organization - Updated Structure

## Overview

The scripts have been completely reorganized with standardized naming, correct port allocations, shared utilities, and a master menu system. **Quarkus DevServices automatically start required infrastructure** (Consul, MySQL, OpenSearch) when running any service, so manual infrastructure startup is optional.

## Quick Start

```bash
# Interactive menu for all operations
./scripts/menu.sh

# Or start any service directly (DevServices will auto-start infrastructure)
./scripts/start-chunker.sh           # Starts chunker + auto-starts Consul, DB, etc.
./scripts/start-platform-registration.sh  # Starts registration service + infrastructure
```

## Script Categories

### **Infrastructure Management (Optional)**
- `devservices-up.sh` - Manually start shared dev infrastructure (optional)
- `devservices-down.sh` - Stop shared dev infrastructure
- `consul-delete.sh` - Clear all Consul data

> **Note**: Infrastructure services (Consul, MySQL, OpenSearch) are automatically started by Quarkus DevServices when you run any service. Manual startup is only needed for testing infrastructure independently.

### **Core Services (38xxx ports)**
- `start-pipestream-engine.sh` - Main orchestrator (38100)
- `start-platform-registration.sh` - Module registry & health (38101)
- `start-repo-service.sh` - Repository management (default 38102, configurable)
- `start-opensearch-manager.sh` - OpenSearch operations (38103)
- `start-mapping-service.sh` - Data mapping & transformation (38104)
- `start-web-proxy.sh` - API Gateway (38106)

### **Processing Modules (39xxx ports)**
- `start-echo.sh` - Echo/test module (39000)
- `start-parser.sh` - Document parsing (39001)
- `start-chunker.sh` - Text chunking (39002)
- `start-embedder.sh` - Vector embedding (39003)
- `start-opensearch-sink.sh` - Vector storage (39004) *[Currently disabled]*

### **Development Tools**
- `start-dev-tools.sh` - Web management UI & developer tools (38107)
- `create-container.sh` - Docker container management

### **Testing & Utilities**
- `test-pipeline.sh` - End-to-end pipeline testing
- `test-opensearch-manager.sh` - OpenSearch manager testing
- `regenerate-grpc-stubs.sh` - Regenerate gRPC stubs
- `installers/install-node-deps.sh` - Install Node.js dependencies

### **Orchestration**
- `quick-start.sh` - Quick start everything
- `start-services.sh` - Start all services
- `stop-services.sh` - Stop all services

### **Master Control**
- `menu.sh` - Interactive menu system for all operations

## DevServices Integration

**Quarkus DevServices automatically handle infrastructure:**

- ✅ **Consul** (8500) - Service discovery
- ✅ **MySQL** (3306) - Database
- ✅ **OpenSearch** (9200) - Search engine
- ✅ **Apicurio Registry** (8081) - Schema registry
- ✅ **Kafka** (9094) - Message streaming

**This means:**
- No need to manually start infrastructure before running services
- Each service automatically gets the required dependencies
- Infrastructure is shared across all running services
- Clean shutdown when all services stop

## Port Alignment

All scripts now use the correct ports as defined in `docs/Port_allocations.md`:

| Service | Port | Status |
|---------|------|--------|
| **Core Services** |
| PipeStream Engine | 38100 | ✅ Fixed |
| Platform Registration | 38101 | ✅ Fixed (was 39101) |
| Repository Service | 38102 | ✅ Fixed |
| OpenSearch Manager | 38103 | ✅ Fixed |
| Mapping Service | 38104 | ✅ Fixed |
| Web Proxy | 38106 | ✅ Fixed |
| Dev Tools | 38107 | ✅ Fixed |
| **Processing Modules** |
| Echo | 39000 | ✅ Fixed (was 39100) |
| Parser | 39001 | ✅ Fixed (was 39101) |
| Chunker | 39002 | ✅ Fixed (was 39102) |
| Embedder | 39003 | ✅ Correct |
| OpenSearch Sink | 39004 | ✅ Created |

## Shared Utilities

All scripts now use `shared-utils.sh` which provides:

- **Consistent styling** with colored output
- **Port checking** to detect conflicts
- **Infrastructure status checking** (informational only)
- **Standardized Quarkus startup** with proper error handling
- **Service readiness waiting** with health checks
- **DevServices awareness** - no forced dependency checking

## Usage Examples

### **Basic Workflow (Recommended)**
```bash
# Just start any service - infrastructure auto-starts
./scripts/start-chunker.sh
# Quarkus DevServices will automatically start Consul, MySQL, OpenSearch, etc.
```

### **Using the Menu**
```bash
./scripts/menu.sh
# Select options from interactive menu
# Infrastructure services marked as "optional" since they auto-start
```

### **Development Workflow**
```bash
# Start services directly - no infrastructure prep needed
./scripts/start-platform-registration.sh  # Auto-starts infrastructure
./scripts/start-repo-service.sh           # Reuses existing infrastructure
./scripts/start-echo.sh                   # Reuses existing infrastructure
./scripts/start-chunker.sh                # Reuses existing infrastructure

# Test the pipeline
./scripts/test-pipeline.sh
```

### **Manual Infrastructure (Optional)**
```bash
# Only if you want to start infrastructure independently
./scripts/devservices-up.sh

# Clear Consul data if needed
./scripts/consul-delete.sh

# Stop infrastructure manually
./scripts/devservices-down.sh
```

## Features

### **DevServices Integration**
- ✅ Automatic infrastructure startup with any service
- ✅ Shared infrastructure across all services
- ✅ No manual dependency management required
- ✅ Clean resource management

### **Automatic Checks**
- ✅ Port conflict detection
- ✅ Infrastructure status display (informational)
- ✅ Service health monitoring
- ✅ Graceful handling of existing services

### **User Experience**
- ✅ Colored output with status indicators
- ✅ Clear information about DevServices auto-start
- ✅ Interactive confirmations for conflicts
- ✅ Progress indicators for startup

### **Consistency**
- ✅ Standardized naming convention
- ✅ Uniform startup process
- ✅ Consistent environment variable handling
- ✅ Shared utility functions

## Platform Registration Service Configuration

The platform registration service includes specific environment variables for proper operation:

```bash
export PLATFORM_REGISTRATION_HOST="${PLATFORM_REGISTRATION_HOST:-172.17.0.1}"
export PIPELINE_CONSUL_HOST="${PIPELINE_CONSUL_HOST:-localhost}"
export PIPELINE_CONSUL_PORT="${PIPELINE_CONSUL_PORT:-8500}"
```

These ensure proper service discovery and registration with Consul.

## Changes Made

### **Key Corrections**
- ✅ **Database**: Updated all references from PostgreSQL to MySQL (port 3306)
- ✅ **Platform Registration**: Restored missing environment variables (PLATFORM_REGISTRATION_HOST, PIPELINE_CONSUL_HOST, PIPELINE_CONSUL_PORT)
- ✅ **DevServices Integration**: Removed forced devservices dependency checking
- ✅ **Port Alignment**: Fixed all service ports to match documentation

### **Deleted Scripts (8 removed)**
- `consul-dev.sh`, `start-consul-dev.sh`, `stop-consul-dev.sh` (redundant)
- `start-opensearch-sink-container.sh`, `start-opensearch-sink-devcontainer.sh`, `start-opensearch-sink-remote-dev.sh` (variants)
- `start-pipedoc-repository.sh`, `draft-dev.sh` (legacy/deprecated)

### **Renamed Scripts (9 renamed)**
- `mapping-devMode.sh` → `start-mapping-service.sh`
- `registration-devMode.sh` → `start-registration-service.sh`
- `echo-dev.sh` → `start-echo.sh`
- `parser-dev.sh` → `start-parser.sh`
- `embedder-dev.sh` → `start-embedder.sh`
- `start-shared-devservices.sh` → `devservices-up.sh`
- `stop-shared-devservices.sh` → `devservices-down.sh`
- `clear-consul.sh` → `consul-delete.sh`
- `start-developer-frontend.sh` → `start-dev-tools.sh`

### **Updated Scripts (All service scripts)**
- Fixed port configurations to match documentation
- Added shared utilities integration
- Removed unnecessary devservices dependency checking
- Added DevServices awareness messaging
- Restored missing environment variables
- Updated database references to MySQL
- Improved error handling and user feedback

### **Created Scripts (4 new)**
- `shared-utils.sh` - Common utilities for all scripts
- `start-opensearch-sink.sh` - Missing module script
- `create-container.sh` - Docker container management
- `menu.sh` - Master interactive menu

## Troubleshooting

### **Common Issues**

**Port Already in Use:**
```bash
# Scripts will detect and warn about port conflicts
# Follow the prompts to continue or stop conflicting services
```

**Infrastructure Issues:**
```bash
# DevServices handles this automatically, but if needed:
./scripts/consul-delete.sh     # Clear Consul data
./scripts/devservices-down.sh  # Stop infrastructure
./scripts/devservices-up.sh    # Restart infrastructure
```

**Platform Registration Service Issues:**
```bash
# Check environment variables are set correctly
echo $PLATFORM_REGISTRATION_HOST  # Should be 172.17.0.1
echo $PIPELINE_CONSUL_HOST         # Should be localhost
echo $PIPELINE_CONSUL_PORT         # Should be 8500
```

**Service Won't Start:**
```bash
# Check if port is available
lsof -i :39002  # Example for chunker

# Check DevServices logs in the service output
# Quarkus will show DevServices startup progress
```

### **Service Status Check**
```bash
# Use the menu option 4 or check manually
./scripts/menu.sh
# Select "4) Show Service Status"
```

## Migration from Old Scripts

If you have bookmarks or automation using old script names:

```bash
# Old → New
mapping-devMode.sh → start-mapping-service.sh
echo-dev.sh → start-echo.sh
clear-consul.sh → consul-delete.sh
start-shared-devservices.sh → devservices-up.sh
```

## Best Practices

### **Recommended Workflow**
1. **Just start the service you need** - DevServices handles the rest
2. **Use the menu** for discovery and convenience
3. **Check status** if something seems wrong
4. **Clear Consul** if services aren't registering properly

### **Development Tips**
- **Single service development**: Just run the service script
- **Multi-service testing**: Start services in any order
- **Clean slate**: Use `consul-delete.sh` to reset service registry
- **Infrastructure issues**: Restart with `devservices-down.sh` then `devservices-up.sh`

## Future Enhancements

- **Health monitoring dashboard** in the menu
- **Batch operations** for starting/stopping service groups
- **Configuration validation** before startup
- **Log aggregation** and viewing
- **Performance monitoring** integration
- **DevServices status integration** in menu
