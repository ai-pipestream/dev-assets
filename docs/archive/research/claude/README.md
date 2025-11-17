# Pipeline Engine Build Restructuring Documentation

**Date**: 2025-10-23
**Status**: Planning Phase
**Goal**: Transform monolithic build into independent, CI/CD-ready microservices

---

## Overview

This directory contains comprehensive documentation for restructuring the Pipeline Engine build system from a tightly-coupled monolithic Gradle build to independent, publishable components with full CI/CD automation.

## Documentation Index

### 1. [Build Restructuring Plan](./build-restructuring-plan.md)

**Complete migration guide** covering:
- Current state analysis and pain points
- Proposed mono-repo with independent builds architecture
- Step-by-step migration plan (10 phases)
- GitHub Packages setup
- Directory structure changes
- Success criteria and risks

**Start here if**: You want to understand the overall strategy and migration approach.

**Key sections**:
- Phase-by-phase migration steps
- New directory structure
- Repository configuration examples
- Rollout schedule (4 weeks)

### 2. [Testing Strategy](./testing-strategy.md)

**Comprehensive testing approach** covering:
- Test pyramid (70% unit, 20% integration, 10% E2E)
- Testcontainers for integration tests
- WireMock for gRPC mocking
- Dev mode testing workflow
- Frontend testing (Jest, Playwright)
- Testing per service breakdown

**Start here if**: You want to understand how to write tests for isolated services.

**Key sections**:
- Unit test examples with WireMock
- Integration test examples with Testcontainers
- Service-specific testing requirements
- CI/CD test integration

### 3. [Local Development Guide](./local-development.md)

**Day-to-day development workflows** covering:
- Prerequisites and first-time setup
- Working with different components (gRPC, libraries, apps, frontend)
- Common development tasks
- Troubleshooting guide
- IDE configuration
- Tips and tricks

**Start here if**: You're a developer setting up your local environment or working on a specific component.

**Key sections**:
- Setup script usage
- Dev mode workflows
- Working with proto changes
- Debugging tips

### 4. [CI/CD Workflows](./cicd-workflows.md)

**GitHub Actions automation** covering:
- Publishing strategy (Maven, Docker)
- Build phases and dependencies
- Workflow templates for each component type
- Docker registry configuration
- Rollout plan

**Start here if**: You're setting up or modifying GitHub Actions workflows.

**Key sections**:
- gRPC stubs workflow
- Libraries workflow
- platform-registration-service workflow (Docker)
- Generic application/module templates

---

## Quick Start

### For Developers

**First time setup**:
```bash
# 1. Clone repo
git clone <repo-url>
cd pipeline-engine-refactor

# 2. Run setup script
./dev-infrastructure/scripts/setup-local-dev.sh

# 3. Start infrastructure
cd dev-infrastructure
docker compose -f compose-devservices.yml up -d

# 4. Start your service
cd ../applications/account-manager
./gradlew quarkusDev
```

**Read**: [Local Development Guide](./local-development.md)

### For Build Engineers

**Migration execution**:

1. **Read**: [Build Restructuring Plan](./build-restructuring-plan.md) - Phases 0-10
2. **Start with**: Phase 1 (Restructure Libraries)
3. **Then**: Phase 2 (Proof of Concept - account-manager)
4. **Follow**: Phases 3-10 sequentially

**Key tasks**:
- Update Gradle builds for independence
- Configure GitHub Packages
- Create CI/CD workflows
- Test and validate each phase

### For QA/Test Engineers

**Understanding test strategy**:

1. **Read**: [Testing Strategy](./testing-strategy.md)
2. **Focus on**: Testcontainers setup for integration tests
3. **Learn**: WireMock for mocking external services
4. **Practice**: Writing tests for each service type

**Key concepts**:
- Test pyramid: 70/20/10 split
- Each service tests independently
- No shared test infrastructure (except dev mode)

---

## Migration Status

### Phase 0: Preparation ✅
- [x] Documentation created
- [x] GitHub Packages access configured
- [ ] Baseline build verified

### Phase 1: Restructure Libraries
- [ ] Create separate libraries build
- [ ] Move BOM and libraries
- [ ] Test libraries build
- [ ] Create libraries CI workflow

### Phase 2: Proof of Concept (account-manager)
- [ ] Create independent build
- [ ] Add Testcontainers
- [ ] Test local build
- [ ] Create CI workflow

### Phase 3: Update Root Build
- [ ] Remove migrated projects from root
- [ ] Update dependency substitution
- [ ] Test remaining root build

### Phase 4: Migrate Applications
- [ ] connector-service
- [ ] repo-service
- [ ] opensearch-manager
- [ ] mapping-service
- [ ] linear-engine
- [ ] platform-registration-service (+ Docker)

### Phase 5: Migrate Modules
- [ ] parser
- [ ] chunker
- [ ] embedder
- [ ] echo

### Phase 6: Node/Frontend
- [ ] Move to root level
- [ ] Update proto sync
- [ ] Publish shared libraries
- [ ] Create CI workflows

### Phase 7: gRPC GitHub Packages
- [ ] Update grpc build
- [ ] Create CI workflow
- [ ] Test publishing

### Phase 8: Dev Infrastructure
- [ ] Move compose files
- [ ] Create setup scripts
- [ ] Update documentation

### Phase 9: Documentation
- [ ] Update root README
- [ ] Create BUILD_ORDER_NEW.md
- [ ] Update all docs

### Phase 10: Validation
- [ ] Full clean build test
- [ ] Quarkus dev mode test
- [ ] CI workflows test
- [ ] Team training

---

## Key Decisions

### Architecture Decisions

1. **Mono-repo vs Multi-repo**: **Mono-repo with independent builds**
   - Rationale: Proto files are shared API contract, easier to keep in sync
   - Benefits: Change proto → test all affected services in one PR
   - Trade-off: Larger repo, but simpler dependency management

2. **Publishing**: **GitHub Packages for Maven & npm, GHCR for Docker**
   - Rationale: Free, integrated with GitHub, unlimited for public repos
   - Alternative considered: Docker Hub (rate limits), Nexus (self-hosted complexity)

3. **Testing**: **Testcontainers for integration, no shared infrastructure**
   - Rationale: Each service tests independently, more maintainable
   - Trade-off: Slower integration tests, but more reliable

4. **Build Triggers**: **Path-based, no forced cascades**
   - Rationale: Only build what changed, save CI/CD time
   - Future option: Add workflow_dispatch for manual full rebuilds

### Build Order

**Foundation first**:
1. gRPC stubs (everyone needs)
2. Libraries (everyone needs)
3. platform-registration-service (runtime foundation)
4. All other services (parallel)
5. Frontend (depends on backends)

### Local Development

**Maven Local first, GitHub Packages second**:
```gradle
repositories {
    mavenLocal()      // Fast local dev
    githubPackages()  // Published artifacts
    mavenCentral()
}
```

---

## Success Metrics

### Build Independence
- [ ] Each application builds without root build
- [ ] Each module builds without root build
- [ ] Libraries build independently
- [ ] gRPC builds independently

### CI/CD
- [ ] All components have workflows
- [ ] Workflows trigger on relevant changes only
- [ ] Artifacts publish to GitHub Packages
- [ ] Docker images publish to GHCR

### Local Development
- [ ] Setup script works from clean checkout
- [ ] Quarkus dev mode works for all apps
- [ ] Proto sync is automated
- [ ] Documentation is clear

### Testing
- [ ] Unit tests < 1 minute per service
- [ ] Integration tests use Testcontainers
- [ ] No shared test infrastructure
- [ ] All tests pass in CI/CD

---

## Timeline

**Estimated: 4 weeks**

- **Week 1**: Foundation (gRPC, libraries)
- **Week 2**: Core service (platform-registration-service)
- **Week 3-4**: Remaining services & modules
- **Week 5**: Frontend & validation

---

## Getting Help

### Questions about specific topics:

- **Build system**: See [Build Restructuring Plan](./build-restructuring-plan.md)
- **Testing**: See [Testing Strategy](./testing-strategy.md)
- **Local dev**: See [Local Development Guide](./local-development.md)
- **CI/CD**: See [CI/CD Workflows](./cicd-workflows.md)

### Issues or blockers:

1. Check [Troubleshooting](./local-development.md#troubleshooting) section
2. Check GitHub Issues for known problems
3. Ask in team chat
4. Create new GitHub Issue with details

---

## Next Steps

**For immediate start**:

1. ✅ **Read this README** (you're here!)
2. 📖 **Read** [Build Restructuring Plan](./build-restructuring-plan.md) - Phase 0
3. 🔧 **Run** setup script: `./dev-infrastructure/scripts/setup-local-dev.sh`
4. ✅ **Verify** baseline build works
5. 🚀 **Start** Phase 1: Restructure Libraries

**For understanding the approach**:

1. Review all 4 documentation files
2. Understand dependency graph
3. Plan your contribution area
4. Start with proof-of-concept (account-manager)

---

## Contributing

When updating this documentation:

1. Keep all 4 files in sync
2. Update version and date at top of each file
3. Add entries to this README index
4. Test any code examples provided
5. Update migration status checklist

---

## Appendix: File Sizes

Approximate reading times:

- **build-restructuring-plan.md**: 45-60 minutes (comprehensive)
- **testing-strategy.md**: 30-40 minutes (detailed)
- **local-development.md**: 25-35 minutes (practical)
- **cicd-workflows.md**: 20-30 minutes (technical)
- **README.md** (this file): 10-15 minutes (overview)

**Total**: ~2.5-3 hours for complete read-through

---

**Document Version**: 1.0
**Last Updated**: 2025-10-23
**Maintained By**: Development Team
**Status**: Ready for Review
