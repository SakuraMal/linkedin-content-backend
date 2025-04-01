# API Documentation

This directory contains documentation for the API contracts between the frontend and backend systems. Understanding these contracts is essential for implementing new features without breaking existing functionality.

## Directory Structure

```
api/
├── contracts/
│   ├── video-generation.md  # Core video generation API contract
│   ├── captions.md          # Caption-specific API details
│   └── ...                  # Other feature-specific contracts
└── README.md                # This file
```

## Purpose

These API contract documents serve multiple purposes:

1. **Documentation**: They document the current working API contracts between frontend and backend
2. **Reference**: Developers can reference them when implementing new features
3. **Guidelines**: They provide guidelines for maintaining backward compatibility
4. **Testing**: They inform the creation of test cases for API validation

## Using These Documents

When implementing new features or modifying existing ones:

1. **Review the contract** for the relevant feature area
2. **Check for compatibility** between your changes and the existing contract
3. **Update the contract** if your changes extend or modify the API
4. **Test against the contract** to ensure your implementation meets the specifications

## Key Contracts

- **Video Generation**: Core video generation endpoint contract
- **Captions**: Caption-specific API parameters and processing details

## Versioning

Currently, the API doesn't use explicit versioning. As we build more features, we should consider adding formal versioning to allow for smoother transitions between API versions.

## Contribution Guidelines

When updating these contracts:

1. Maintain backward compatibility where possible
2. Clearly mark new or changed fields
3. Document the date of changes
4. Include examples where helpful
5. Consider impacts on existing clients 