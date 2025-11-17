# Repository Service Architecture - Section 3: Data Model - Drive Entity

## Drive Entity

**Final Design (Database Entity):**
```java
@Entity
@Table(name = "drives")
public class Drive extends PanacheEntity {
    @Column(unique = true, nullable = false)
    public String name;                    // Customer-facing drive name
    
    @Column(name = "bucket_name", unique = true, nullable = false)
    public String bucketName;              // Actual S3 bucket name
    
    @Column(name = "customer_id", nullable = false)
    public String customerId;              // Customer identifier for multi-tenancy and billing
    
    @Column(name = "region")
    public String region;                  // S3 region (optional)
    
    @Column(name = "credentials_ref")
    public String credentialsRef;          // String reference to external secret management
    
    @Column(name = "status_id")
    public Long statusId;                  // Foreign key to drive_status lookup table
    
    @Column(name = "description")
    public String description;             // Drive description
    
    @Column(name = "created_at")
    public OffsetDateTime createdAt;
    
    @Column(name = "metadata")
    public String metadata;                 // JSON metadata for unstructured data
}
```

**Protobuf Definition:**
```protobuf
message Drive {
  int64 id = 1;                    // Database primary key
  string name = 2;                 // Drive name (no colons allowed)
  string bucket_name = 3;          // Actual S3 bucket name
  string customer_id = 4;          // Customer identifier for multi-tenancy and billing
  string region = 5;               // S3 region (optional)
  string credentials_ref = 6;      // String reference to external secret management
  int64 status_id = 7;             // Foreign key to drive_status lookup table
  string description = 8;          // Human-readable description
  google.protobuf.Timestamp created_at = 9;
  string metadata = 10;            // JSON metadata for unstructured data
}
```

@Entity
@Table(name = "drive_status")
public class DriveStatus extends PanacheEntity {
    @Column(unique = true, nullable = false)
    public String code;                    // Status code (ACTIVE, INACTIVE, etc.)
    
    @Column(nullable = false)
    public String description;             // Human-readable description
    
    @Column(name = "is_active")
    public Boolean isActive = true;        // Whether this status represents an active drive
}
```

## Database Schema

```sql
CREATE TABLE drive_status (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    code VARCHAR(50) UNIQUE NOT NULL,
    description VARCHAR(255) NOT NULL,
    is_active BOOLEAN DEFAULT true,
    INDEX idx_drive_status_code (code)
);

CREATE TABLE drives (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(255) UNIQUE NOT NULL,
    bucket_name VARCHAR(255) UNIQUE NOT NULL,
    customer_id VARCHAR(255) NOT NULL,
    region VARCHAR(50),
    credentials_ref VARCHAR(255),
    status_id BIGINT NOT NULL,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    metadata JSON,
    FOREIGN KEY (status_id) REFERENCES drive_status(id),
    INDEX idx_drives_customer (customer_id),
    INDEX idx_drives_status (status_id),
    INDEX idx_drives_name (name)
);

-- Initial status values
INSERT INTO drive_status (code, description, is_active) VALUES 
('ACTIVE', 'Drive is active and available', true),
('INACTIVE', 'Drive is inactive (lazy delete)', false);
```

## Key Features

1. **Lookup Table**: DriveStatus table for flexible status management
2. **String Reference**: Simple credentials reference for external secret management
3. **Flexible Region**: Optional region field for different S3-compatible providers
4. **JSON Metadata**: Flexible metadata storage for unstructured data
5. **Extensible**: Easy to add new statuses without schema changes