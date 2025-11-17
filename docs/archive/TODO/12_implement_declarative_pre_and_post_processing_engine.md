## 12. Implement Declarative Pre- and Post-Processing Engine

**Goal:** Enhance the `ProtoFieldMapper` to support advanced transformations like field joining and filtering, and integrate it into the `pipestream-engine` to be configured on a per-pipeline basis.

### Ticket 12.1: Enhance `ProtoFieldMapper` to Support Field Joining

**Title:** Feature: Add a `JOIN` function to `ProtoFieldMapper`

**Description:**
Extend the `ProtoFieldMapper` to support a `JOIN` function that can concatenate multiple source fields (or literals) into a single target field, with a specified separator.

**Tasks:**
1.  Update the `RuleParser` to recognize a new function-style syntax, e.g., `target.field = JOIN(" ", source.field1, "literal", source.field2)`.
2.  In the `FieldAccessor`, enhance the `getValue` method to detect the `JOIN(...)` function.
3.  When `JOIN` is detected, the accessor should:
    *   Parse the arguments within the parentheses.
    *   The first argument should be the separator string.
    *   Recursively call `getValue` for each subsequent argument to resolve its value (whether it's a path or a literal).
    *   Concatenate the resolved values using the separator.
    *   Return the final joined string.

### Ticket 12.2: Enhance `ProtoFieldMapper` to Support Filtering

**Title:** Feature: Add `INCLUDE` and `EXCLUDE` rules to `ProtoFieldMapper`

**Description:**
Extend the `ProtoFieldMapper` to support `INCLUDE` and `EXCLUDE` rules for fine-grained control over which fields are present in the final message.

**Tasks:**
1.  **EXCLUDE Rule:**
    *   Add a new `EXCLUDE` operation, e.g., `EXCLUDE target.field.to_remove`.
    *   This will be similar to the existing `CLEAR` operation but provides a more explicit and readable syntax for filtering.
    *   Consider adding support for wildcards in the future, e.g., `EXCLUDE target.metadata.*`.
2.  **INCLUDE Rule:**
    *   This is a more complex operation that implies "remove everything else."
    *   Introduce a new rule syntax, e.g., `target = INCLUDE(source, "field1", "field2.nested")`.
    *   The implementation will involve:
        *   Creating a new, empty instance of the target message.
        *   Iterating through the specified fields to include.
        *   For each field, read the value from the source and set it on the new target message.
        *   Replacing the original target message with this new, filtered instance.

### Ticket 12.3: Integrate `ProtoFieldMapper` into the Pipestream Engine

**Title:** Feature: Integrate `ProtoFieldMapper` into the `pipestream-engine`

**Description:**
Allow pipelines to be configured with pre- and post-processing mapping rules that are executed by the `pipestream-engine`.

**Tasks:**
1.  Update the `PipelineStepConfig` model to include two new optional fields: `pre_processing_rules` and `post_processing_rules`, both of which are lists of strings.
2.  In the `PipeStreamEngineImpl`, before processing a step, check if `pre_processing_rules` are defined. If so, use an instance of `ProtoFieldMapper` to apply the rules to the incoming `PipeDoc`.
3.  After processing a step, check if `post_processing_rules` are defined. If so, use the `ProtoFieldMapper` to apply the rules to the outgoing `PipeDoc`.
4.  Update the pipeline configuration JSON schema and documentation to include these new fields.
