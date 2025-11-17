# Module Frontend Rendering Guide

This guide explains how to create module frontends that integrate seamlessly with the Pipeline Engine's rendering system.

## Overview

The Pipeline Engine uses a **schema-driven approach** to render module configuration interfaces. Your module's OpenAPI 3.1 schema becomes the source of truth for how the frontend form will appear and behave.

## Core Philosophy

- **Pure OpenAPI 3.1** - Your schema drives the entire frontend experience
- **JSONForms Integration** - Forms are auto-generated from your schema
- **Reference Implementation** - Our chunker/parser modules show the exact pattern
- **Test Proxy Available** - See exactly how your schema renders before deployment

## Standards and Requirements

### 1. OpenAPI 3.1 Schema Requirements

Your module MUST provide:
- **Schema endpoint**: `GET /api/{module}/service/config`
- **Processing endpoint**: `POST /api/{module}/service/process-json` 
- **OpenAPI 3.1 compliant** configuration record
- **JSON Schema Draft 7 compatible** (automatic with OpenAPI 3.1)

### 2. Configuration Record Structure

```java
@Schema(
    name = "YourModuleConfig",
    description = "Configuration for your module operations",
    examples = {
        """
        {
            "config_id": "example-config",
            "processingOptions": {
                "setting1": "value1",
                "setting2": true
            }
        }
        """
    }
)
public record YourModuleConfig(
    @JsonProperty("config_id")
    @Schema(description = "Unique identifier for this configuration")
    String configId,
    
    @JsonProperty("processingOptions") 
    @Schema(description = "Core processing settings")
    ProcessingOptions processingOptions
) {
    // Static factory methods for common configurations
    public static YourModuleConfig defaultConfig() { ... }
}
```

### 3. Supported OpenAPI Extensions

For rendering customization while maintaining schema compliance:

#### Field Control
- `x-hidden: true` - Hide field from form (used for computed/internal fields)
- `x-readonly: true` - Display field as read-only in form
- `x-display-order: 1` - Control field ordering (lower numbers first)

#### UI Hints  
- `x-component-type: "textarea"` - Render as textarea instead of text input
- `x-component-type: "select"` - Render as dropdown (requires enum values)
- `x-display-name: "Custom Label"` - Override field label in form

#### Validation Display
- `x-validation-message: "Custom error message"` - Custom validation text
- `x-help-text: "Field explanation"` - Help text displayed below field

#### Example Usage:
```java
@Schema(
    description = "Large text content for processing",
    example = "This is sample text...",
    extensions = {
        @Extension(name = "x-component-type", value = "textarea"),
        @Extension(name = "x-help-text", value = "Enter the text you want to process"),
        @Extension(name = "x-display-order", value = "1")
    }
)
String textContent
```

### 4. Endpoint Implementation

Your module must provide these endpoints:

#### Schema Endpoint
```java
@GET
@Path("/config")
public Uni<Response> getConfig() {
    Optional<String> schema = schemaExtractorService.extractYourModuleConfigSchemaForValidation();
    return Uni.createFrom().item(
        Response.ok(schema.orElse("{}")).type(MediaType.APPLICATION_JSON).build()
    );
}
```

#### Processing Endpoint
```java
@POST  
@Path("/process-json")
@Consumes(MediaType.APPLICATION_JSON)
public Uni<Response> processWithJsonConfig(Map<String, Object> request) {
    // Extract config and text from request
    YourModuleConfig config = objectMapper.convertValue(request.get("config"), YourModuleConfig.class);
    String text = (String) request.get("text");
    
    // Process using your module's gRPC service logic
    // Return standardized response format
}
```

## Form Rendering Flow

1. **Frontend loads** - Calls `GET /api/{module}/service/config`
2. **Schema received** - OpenAPI 3.1 JSON schema returned
3. **JSONForms generates** - Auto-creates form from schema
4. **User interacts** - Fills out dynamically generated form
5. **Submission** - Form data sent as pure JSON to processing endpoint
6. **Processing** - Backend validates JSON against schema and processes
7. **Results displayed** - Response shown in standardized format

## Testing Your Schema

### Local Testing
Use your module's Vue.js frontend (follow chunker/parser pattern):
1. Start your module in dev mode
2. Navigate to `http://localhost:{port}/`
3. Test Config Card with various inputs
4. Verify form rendering matches expectations

### Reference Proxy Testing  
Use our reference proxy container to see exactly how the Pipeline Engine will render your schema:
```bash
# TODO: Proxy container setup instructions will be provided
docker run -p 8080:8080 pipeline-module-proxy --schema-url=http://your-module/api/service/config
```

## Best Practices

### Schema Design
- **Use descriptive field names** - they become form labels
- **Provide good examples** - shown in form placeholders  
- **Include validation constraints** - enforced in form and backend
- **Nest related fields** - creates logical form sections
- **Use enums for choices** - automatically become dropdowns

### Field Organization
- **Group related settings** into nested objects
- **Use logical ordering** with `x-display-order` when needed
- **Hide internal fields** with `x-hidden: true`
- **Provide help text** for complex fields

### Error Handling
- **Validate early** - use schema validation before processing
- **Provide clear errors** - match field names to schema properties
- **Graceful degradation** - handle partial failures appropriately

## Migration from Custom Forms

If you have existing custom form logic:

1. **Extract your form fields** into OpenAPI schema properties
2. **Add appropriate validation** constraints and examples
3. **Replace custom endpoints** with schema-driven ones
4. **Test rendering** with JSONForms
5. **Refine with extensions** if needed

The goal is **zero custom form code** - everything driven by your OpenAPI schema.

## Reference Implementations

See these modules for complete examples:
- **Chunker**: `/modules/chunker/` - Text processing module
- **Parser**: `/modules/parser/` - Document parsing module

Both follow the identical pattern and can be used as templates for your own module frontend integration.