# Docker Bridge IP Detection

## Overview

The Pipeline Engine services need to register with Consul using an IP address that Docker containers can reach. This IP varies across platforms (Linux, macOS, Windows) and Docker setups. The system now automatically detects the correct Docker bridge IP for service registration.

## Problem Statement

When services register with Consul, they need to provide a host IP that:
1. **Docker containers can reach** (for inter-service communication)
2. **Is accessible from the host** (for development and testing)
3. **Works across platforms** (Linux, macOS, Windows)

### Platform Differences

| Platform | Common Docker Bridge IP | Notes |
|----------|------------------------|-------|
| **Linux** | `172.17.0.1` | Standard Docker bridge |
| **macOS** | `host.docker.internal` | Docker Desktop special hostname |
| **Windows** | `host.docker.internal` | Docker Desktop special hostname |
| **Custom setups** | Varies | May use different bridge networks |

## Solution: Automatic Detection

The system uses `detect-docker-bridge.sh` to automatically find the correct IP using multiple detection methods.

### Detection Methods (in order)

1. **Docker Bridge Network Gateway**
   ```bash
   docker network inspect bridge --format='{{range .IPAM.Config}}{{.Gateway}}{{end}}'
   ```

2. **docker0 Interface (Linux)**
   ```bash
   ip route show | grep docker0 | grep -E 'src [0-9.]+' | sed -n 's/.*src \([0-9.]*\).*/\1/p'
   ```

3. **host.docker.internal Resolution**
   ```bash
   docker run --rm alpine nslookup host.docker.internal
   ```

4. **Container Default Gateway**
   ```bash
   docker run --rm alpine route -n | grep '^0.0.0.0' | awk '{print $2}'
   ```

5. **Platform-specific Fallbacks**
   - Linux: `172.17.0.1`
   - macOS: `host.docker.internal`
   - Windows: `host.docker.internal`

## Usage

### Automatic (Recommended)

All service scripts now automatically detect and use the correct Docker bridge IP:

```bash
./scripts/start-platform-registration.sh
# Automatically detects and uses correct Docker bridge IP
```

### Manual Testing

Test the detection system:

```bash
# Test detection methods
./scripts/test-docker-bridge.sh

# Get just the IP
./scripts/detect-docker-bridge.sh

# Test with export
./scripts/detect-docker-bridge.sh export
echo $DOCKER_BRIDGE_IP
```

### Override if Needed

You can still override the detection by setting environment variables:

```bash
# Override for platform registration
export PLATFORM_REGISTRATION_HOST="192.168.1.100"
./scripts/start-platform-registration.sh

# Override for all modules
export MODULE_HOST="192.168.1.100"
./scripts/start-chunker.sh
```

## Integration with Scripts

### Service Scripts

All service scripts now use the `set_registration_host` function:

```bash
# In start-platform-registration.sh
set_registration_host "platform-registration" "PLATFORM_REGISTRATION_HOST"

# In start-chunker.sh  
set_registration_host "module" "MODULE_HOST"
```

### Shared Utilities

The `shared-utils.sh` provides:

- `get_docker_bridge_ip()` - Returns detected IP
- `set_registration_host(service, env_var)` - Sets environment variable with detected IP

### Environment Variables Set

| Service | Environment Variable | Default Detection |
|---------|---------------------|-------------------|
| Platform Registration | `PLATFORM_REGISTRATION_HOST` | Docker bridge IP |
| Repository Service | `REPOSITORY_SERVICE_HOST` | Docker bridge IP |
| Mapping Service | `MAPPING_SERVICE_HOST` | Docker bridge IP |
| OpenSearch Manager | `OPENSEARCH_MANAGER_HOST` | Docker bridge IP |
| PipeStream Engine | `PIPESTREAM_ENGINE_HOST` | Docker bridge IP |
| All Modules | `MODULE_HOST` | Docker bridge IP |

## Troubleshooting

### Detection Issues

**Problem**: Detection fails or returns wrong IP
```bash
# Test detection manually
./scripts/test-docker-bridge.sh

# Check Docker setup
docker info
docker network ls
docker network inspect bridge
```

**Solution**: Override with correct IP
```bash
export PLATFORM_REGISTRATION_HOST="your.correct.ip"
```

### Connectivity Issues

**Problem**: Services can't reach each other
```bash
# Test connectivity from container
docker run --rm alpine ping -c 1 172.17.0.1

# Check if IP is reachable from host
ping -c 1 172.17.0.1
```

**Solution**: Verify Docker network configuration
```bash
# Check Docker bridge network
docker network inspect bridge

# Restart Docker if needed (varies by platform)
```

### Platform-Specific Issues

#### Linux
- **Issue**: `docker0` interface not found
- **Solution**: Check if Docker is using custom bridge network
- **Command**: `ip addr show docker0`

#### macOS/Windows (Docker Desktop)
- **Issue**: `host.docker.internal` not resolving
- **Solution**: Update Docker Desktop or use IP address
- **Command**: `nslookup host.docker.internal`

#### Custom Docker Setups
- **Issue**: Non-standard bridge network
- **Solution**: Override with correct network gateway
- **Command**: `docker network inspect your-network`

## Configuration Examples

### Development (Auto-detection)
```bash
# Just start services - IP is auto-detected
./scripts/start-platform-registration.sh
./scripts/start-chunker.sh
```

### Production Override
```bash
# Set specific IPs for production
export PLATFORM_REGISTRATION_HOST="10.0.1.100"
export MODULE_HOST="10.0.1.100"

./scripts/start-platform-registration.sh
./scripts/start-chunker.sh
```

### Docker Compose Override
```yaml
# docker-compose.yml
services:
  platform-registration:
    environment:
      - PLATFORM_REGISTRATION_HOST=172.18.0.1  # Custom bridge IP
```

## Validation

### Test Detection
```bash
# Run comprehensive test
./scripts/test-docker-bridge.sh

# Expected output:
# ✅ Docker bridge IP detected: 172.17.0.1
# ✅ Detection method: Docker bridge network gateway
# ✅ Container can reach 172.17.0.1
```

### Verify Service Registration
```bash
# Start a service
./scripts/start-platform-registration.sh

# Check Consul registration
curl http://localhost:8500/v1/catalog/services

# Verify service details
curl http://localhost:8500/v1/catalog/service/platform-registration-service
```

## Benefits

### Cross-Platform Compatibility
- ✅ Works on Linux, macOS, Windows
- ✅ Handles Docker Desktop and native Docker
- ✅ Adapts to custom network configurations

### Developer Experience
- ✅ No manual IP configuration needed
- ✅ Automatic detection with fallbacks
- ✅ Clear error messages and troubleshooting

### Reliability
- ✅ Multiple detection methods
- ✅ Platform-specific fallbacks
- ✅ Validation and connectivity testing

### Flexibility
- ✅ Easy to override when needed
- ✅ Environment variable support
- ✅ Integration with existing scripts
