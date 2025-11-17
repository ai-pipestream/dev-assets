# Database Separation Plan

**Date:** 2025-10-22
**Owner:** Cheetah (AI Assistant)
**Status:** Planning - NO CODING YET

## Problem Statement

Currently, all three services (account-manager, connector-service, repo-service) share a single database (`pipeline_dev`), which causes:

1. **Flyway version conflicts** - Both connector-service and repo-service try to manage schema with different strategies
2. **Migration ordering issues** - Shared `flyway_schema_history` table causes confusion
3. **Tight coupling** - Services cannot evolve independently
4. **Deployment complexity** - Cannot update one service's schema without affecting others

## Root Cause

From the error analysis:
- **connector-service** uses Hibernate `update` strategy (no Flyway in dev)
- **repo-service** uses Flyway migrations
- Both share `pipeline_dev` database
- Flyway tracks all migrations but connector-service doesn't register its versions

## Solution: Separate Databases

Each service gets its own database:
- `pipeline_account_dev` for account-manager
- `pipeline_connector_dev` for connector-service
- `pipeline_repo_dev` for repo-service

**All services will use Flyway for schema management** (following Quarkus best practices)

## Quarkus Flyway Best Practices (from guide)

1. **Required dependencies** (build.gradle):
   ```gradle
   implementation("io.quarkus:quarkus-flyway")
   implementation("io.quarkus:quarkus-jdbc-mysql")
   implementation("org.flywaydb:flyway-mysql") // MySQL-specific
   ```

2. **Configuration pattern** (application.properties):
   ```properties
   # Datasource
   quarkus.datasource.db-kind=mysql
   quarkus.datasource.username=pipeline
   quarkus.datasource.password=password
   %dev.quarkus.datasource.jdbc.url=jdbc:mysql://localhost:3306/{database_name}

   # Flyway
   %dev.quarkus.hibernate-orm.schema-management.strategy=none
   %dev.quarkus.flyway.migrate-at-start=true

   # Test
   %test.quarkus.hibernate-orm.schema-management.strategy=drop-and-create
   %test.quarkus.flyway.migrate-at-start=false

   # Prod
   %prod.quarkus.hibernate-orm.schema-management.strategy=validate
   %prod.quarkus.flyway.migrate-at-start=true
   ```

3. **Migration naming**: `V{version}__{description}.sql`
   - Example: `V1__create_accounts_table.sql`

4. **Dev mode tip**: Set `%dev.quarkus.flyway.clean-at-start=true` for rapid development

## Implementation Plan

### Phase 1: Account-Manager Database Setup

**Database:** `pipeline_account_dev`
**Status:** Already partially configured
**Location:** `applications/account-manager/`

**Tasks:**

1. **Verify build.gradle dependencies**
   - Check for `quarkus-flyway`
   - Check for `flyway-mysql`
   - Check for `quarkus-jdbc-mysql`

2. **Update application.properties**
   ```properties
   %dev.quarkus.datasource.jdbc.url=jdbc:mysql://localhost:3306/pipeline_account_dev
   %dev.quarkus.hibernate-orm.schema-management.strategy=none
   %dev.quarkus.flyway.migrate-at-start=true
   ```

3. **Verify migrations exist**
   - Check `src/main/resources/db/migration/` directory
   - Ensure migrations follow naming convention
   - List current migrations

4. **Test account-manager independently**
   - Run `./gradlew :applications:account-manager:quarkusDev`
   - Verify Flyway runs migrations
   - Verify no errors

**Success Criteria:**
- Account-manager starts successfully
- Flyway migrations run cleanly
- Database `pipeline_account_dev` is created with correct schema

---

### Phase 2: Connector-Service Database Setup

**Database:** `pipeline_connector_dev`
**Status:** Currently uses Hibernate update, needs Flyway migration
**Location:** `applications/connector-service/`

**Current State:**
- Has 3 Flyway migrations: V1, V2, V3
- Uses Hibernate `update` in dev mode
- Migrations NOT being run

**Tasks:**

1. **Verify build.gradle dependencies**
   - Confirm `quarkus-flyway` exists
   - Confirm `flyway-mysql` exists
   - Confirm `quarkus-jdbc-mysql` exists

2. **Update application.properties**
   ```properties
   # Change from:
   %dev.quarkus.hibernate-orm.schema-management.strategy=update
   %dev.quarkus.flyway.migrate-at-start=false

   # To:
   %dev.quarkus.datasource.jdbc.url=jdbc:mysql://localhost:3306/pipeline_connector_dev
   %dev.quarkus.hibernate-orm.schema-management.strategy=none
   %dev.quarkus.flyway.migrate-at-start=true
   %dev.quarkus.flyway.clean-at-start=false
   ```

3. **Review existing migrations**
   - V1__create_connectors_table.sql
   - V2__create_connector_accounts_table.sql
   - V3__add_deletion_tracking.sql
   - Verify they are correct and complete

4. **Test connector-service independently**
   - Run `./gradlew :applications:connector-service:quarkusDev`
   - Verify Flyway creates database and runs migrations
   - Verify tables are created correctly
   - Run existing tests

**Success Criteria:**
- Connector-service starts successfully
- Flyway migrations create `connectors` and `connector_accounts` tables
- All tests pass
- Database `pipeline_connector_dev` exists with correct schema

---

### Phase 3: Repo-Service Database Setup

**Database:** `pipeline_repo_dev`
**Status:** Already uses Flyway, just needs database name change
**Location:** `applications/repo-service/`

**Current State:**
- Already uses Flyway correctly
- Has 11 migrations (V1-V12, excluding removed V11)
- Just needs database renamed

**Tasks:**

1. **Update application.properties**
   ```properties
   # Change from:
   %dev.quarkus.datasource.jdbc.url=jdbc:mysql://localhost:3306/pipeline_dev

   # To:
   %dev.quarkus.datasource.jdbc.url=jdbc:mysql://localhost:3306/pipeline_repo_dev
   ```

2. **Verify build.gradle dependencies**
   - Confirm `quarkus-flyway` exists
   - Confirm `flyway-mysql` exists

3. **Review migrations**
   - List all migrations: V1, V2, V3, ..., V10, V12 (V11 was deleted)
   - Verify order and completeness
   - Check for any references to removed V11

4. **Test repo-service independently**
   - Run `./gradlew :applications:repo-service:quarkusDev`
   - Verify Flyway creates database and runs all migrations
   - Verify no errors
   - Test key operations (drive creation, document upload)

**Success Criteria:**
- Repo-service starts successfully
- Flyway migrations run cleanly
- Database `pipeline_repo_dev` exists with correct schema
- No references to old `pipeline_dev` database

---

### Phase 4: Update Shared Dev Services

**File:** `src/test/resources/compose-devservices.yml`
**Status:** Needs to create all three databases

**Tasks:**

1. **Update MySQL service configuration**
   - Ensure MySQL container creates all three databases on startup
   - Use MySQL init script or environment variables

2. **Create init script** (if needed)
   ```sql
   CREATE DATABASE IF NOT EXISTS pipeline_account_dev;
   CREATE DATABASE IF NOT EXISTS pipeline_connector_dev;
   CREATE DATABASE IF NOT EXISTS pipeline_repo_dev;

   CREATE DATABASE IF NOT EXISTS pipeline_account_test;
   CREATE DATABASE IF NOT EXISTS pipeline_connector_test;
   CREATE DATABASE IF NOT EXISTS pipeline_repo_test;
   ```

3. **Update compose file**
   - Add init script mounting
   - Verify port mappings (3306 for dev, 3307 for test)

**Success Criteria:**
- MySQL container starts with all databases pre-created
- Each service can connect to its own database
- No conflicts between services

---

### Phase 5: Update Test Configurations

**Scope:** All three services
**Status:** Need separate test databases

**Tasks:**

1. **Update test configurations**
   - account-manager: `jdbc:mysql://localhost:3307/pipeline_account_test`
   - connector-service: `jdbc:mysql://localhost:3307/pipeline_connector_test`
   - repo-service: `jdbc:mysql://localhost:3307/pipeline_repo_test`

2. **Update compose-test-services.yml**
   - Ensure test databases are created
   - Use different port (3307) to avoid conflicts with dev

3. **Run all tests**
   - `./gradlew :applications:account-manager:test`
   - `./gradlew :applications:connector-service:test`
   - `./gradlew :applications:repo-service:test`

**Success Criteria:**
- All tests pass
- No database conflicts
- Each service tests independently

---

### Phase 6: Documentation

**Tasks:**

1. **Update README files**
   - Document new database architecture
   - Update setup instructions
   - Document Flyway usage

2. **Update architecture diagrams**
   - Show separate databases
   - Document migration strategy

3. **Create troubleshooting guide**
   - Common Flyway issues
   - How to repair migrations
   - How to reset databases

---

## Migration Checklist (Per Service)

For each service, verify:

- [ ] build.gradle has correct dependencies
- [ ] application.properties uses correct database name
- [ ] Flyway is enabled in dev mode
- [ ] Hibernate schema-management is set to `none` in dev
- [ ] Migrations exist in `src/main/resources/db/migration/`
- [ ] Migrations follow naming convention
- [ ] Service starts without errors
- [ ] Database is created automatically
- [ ] Tables are created correctly
- [ ] Tests pass

## Rollback Plan

If issues arise:

1. **Stop all services**
2. **Drop all new databases**
   ```sql
   DROP DATABASE IF EXISTS pipeline_account_dev;
   DROP DATABASE IF EXISTS pipeline_connector_dev;
   DROP DATABASE IF EXISTS pipeline_repo_dev;
   ```
3. **Recreate original shared database**
   ```sql
   CREATE DATABASE pipeline_dev;
   ```
4. **Revert application.properties changes**
5. **Document issues encountered**

## Testing Strategy

### Unit Testing
- Each service's tests run independently
- Use in-memory or test-specific databases
- No shared state between test runs

### Integration Testing
- Test each service with its own database
- Verify gRPC communication between services
- Test account validation flows

### E2E Testing
- All services running simultaneously
- Each with separate database
- Verify full workflows

## Known Risks

1. **Migration ordering** - Must ensure migrations are idempotent
2. **Data migration** - Any existing dev data will be lost (acceptable for dev)
3. **Test stability** - May uncover hidden dependencies on shared database
4. **Flyway repair** - May need to use repair command if migrations fail

## Success Criteria (Overall)

- [ ] All three services start independently without errors
- [ ] Each service has its own database
- [ ] Flyway migrations run cleanly for all services
- [ ] All unit tests pass
- [ ] All integration tests pass
- [ ] Services can communicate via gRPC
- [ ] No shared database dependencies
- [ ] Documentation is updated

## Next Steps

1. **READ THIS PLAN THOROUGHLY** - Ensure understanding
2. **Start with account-manager** (Phase 1)
3. **Verify success before moving to Phase 2**
4. **Document any issues encountered**
5. **Update plan as needed**

## Notes

- This is a **breaking change for dev environment** - all dev data will be lost
- Production databases are unaffected (different configuration)
- Test databases will be recreated on each test run
- Use `quarkus.flyway.clean-at-start=true` during active development for rapid iteration

## Change Log

- **2025-10-22:** Initial plan created after discovering shared database conflicts
