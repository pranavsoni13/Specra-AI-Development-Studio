# Software Architecture Patterns

Layered architecture separates an application into logical layers such as
presentation, application logic, domain logic, and data access.

A modular monolith keeps multiple logical modules within one deployable
application. It can provide clear separation of responsibilities without
the operational complexity of independently deployed services.

Microservices are independently deployable services. They can be useful
when independent deployment, scaling, team ownership, or service isolation
justify the additional operational complexity.

Architecture style should be selected according to project requirements
rather than choosing distributed architecture by default.