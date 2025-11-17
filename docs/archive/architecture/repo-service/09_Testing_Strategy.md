# Repository Service Architecture - Section 9: Testing Strategy

## Testing Phases

1. **Unit Tests First**: Test individual components in isolation
2. **Quarkus Dev Mode Second**: Verify application runs and Hibernate works
3. **Integration Tests Last**: End-to-end testing with real services

## Test Data Strategy

**Sample Documents:**
- Use existing test documents from:
  - `/modules/parser/src/test/resources/sample_doc_types`
  - `/modules/parser/src/test/resources/test-documents`
- Repository service will provide its own test data
- No need to create separate test fixtures

## S3 Testing Strategy

**MinIO for Integration Tests:**
- Use MinIO for realistic S3 testing
- Test actual upload/download operations
- Verify multi-part uploads work correctly

**Mock S3 for Unit Tests:**
- Mock S3 client for fast unit tests
- Test business logic without S3 dependencies
- Faster test execution

## Database Testing Strategy

**Same MySQL Instance:**
- Use single MySQL instance for all tests
- Change table names per test class for isolation
- Example: `documents_test_class_1`, `documents_test_class_2`
- Avoid database setup/teardown overhead

## Test Configuration

```properties
# Test Database Configuration
%test.quarkus.datasource.db-kind=mysql
%test.quarkus.datasource.username=pipeline
%test.quarkus.datasource.password=password
%test.quarkus.datasource.jdbc.url=jdbc:mysql://localhost:3307/pipeline_test

# Test S3 Configuration (MinIO)
%test.aws.s3.endpoint-override=http://localhost:9000
%test.aws.s3.path-style-access-enabled=true
%test.aws.s3.bucket-name=test-bucket

# Test Hibernate Configuration
%test.quarkus.hibernate-orm.database.generation=none
%test.quarkus.hibernate-orm.log.sql=true
```

## Test Structure

```java
@QuarkusTest
@QuarkusTestResource(WireMockGrpcTestResource.class)
@TestProfile(MockGrpcProfile.class)
public class DocumentServiceTest {
    
    @Inject
    DocumentService documentService;
    
    @Inject
    NodeRepository nodeRepository;
    
    @Test
    void testCreateDocument() {
        // Unit test with mocked S3
        // Test business logic only
    }
    
    @Test
    void testUploadDocument() {
        // Integration test with MinIO
        // Test actual S3 operations
    }
}
```

## Test Isolation

**Table Naming Strategy:**
```java
@QuarkusTest
public class DocumentServiceTest {
    
    @BeforeEach
    void setupTestTables() {
        // Create test-specific tables
        String testTableName = "documents_test_" + getClass().getSimpleName().toLowerCase();
        // Update Hibernate configuration for this test
    }
}
```

## Key Benefits

1. **Phased Approach**: Unit → Dev Mode → Integration
2. **Real Test Data**: Use existing sample documents
3. **MinIO Integration**: Realistic S3 testing
4. **Table Isolation**: Same MySQL, different table names
5. **Fast Unit Tests**: Mock S3 for speed
6. **Realistic Integration**: MinIO for end-to-end testing