## 28. Implement `PipelineTemplateService` for Reusable Pipelines

**Goal:** Implement a `PipelineTemplateService` that allows users to create and share reusable pipeline templates.

### Ticket 28.1: Create the `PipelineTemplateService`

**Title:** Feature: Implement a `PipelineTemplateService` for reusable pipelines

**Description:**
Create a new `@ApplicationScoped` bean called `PipelineTemplateService` that is responsible for managing pipeline templates.

**Tasks:**
1.  The `PipelineTemplateService` should provide methods for creating, reading, updating, and deleting pipeline templates.
2.  A pipeline template should be a reusable pipeline configuration that can be customized with parameters.
3.  Templates should be stored in a persistent data store, such as a database or a Git repository.

### Ticket 28.2: Integrate `PipelineTemplateService` with the Designer

**Title:** Feature: Integrate the `PipelineTemplateService` with the pipeline designer

**Description:**
The pipeline designer should allow users to create new pipelines from templates.

**Tasks:**
1.  In the pipeline designer, add a new view for browsing and searching for pipeline templates.
2.  When a user selects a template, the designer should create a new pipeline configuration based on the template.
3.  The user should then be able to customize the pipeline by providing values for the template parameters.
