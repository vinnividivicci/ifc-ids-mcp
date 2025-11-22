# IDS MCP Server

**AI-powered creation of buildingSMART IDS files with 100% compliance**

An MCP (Model Context Protocol) server that enables AI agents to deterministically create, validate, and manage Information Delivery Specification (IDS) files that are fully compliant with the buildingSMART IDS 1.0 standard.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

<a href="https://glama.ai/mcp/servers/@vinnividivicci/ifc-ids-mcp">
  <img width="380" height="200" src="https://glama.ai/mcp/servers/@vinnividivicci/ifc-ids-mcp/badge" alt="IDS Server MCP server" />
</a>

## Features

- ✅ **100% IDS 1.0 Compliant** - All exports validate against official XSD schema
- ✅ **IfcTester Integration** - Uses the official IfcOpenShell library
- ✅ **FastMCP Context-Based Sessions** - Automatic session management
- ✅ **Test-Driven Development** - 95%+ code coverage with comprehensive tests
- ✅ **Deterministic Output** - Same input always produces identical output
- ✅ **Type-Safe** - Full type hints with Pydantic validation

## Quick Start

### Installation

```bash
# Clone repository
git clone https://github.com/Quasar-Consulting-Group/ifc-ids-mcp.git
cd ifc-ids-mcp

# Install dependencies
pip install -r requirements.txt

# Install in development mode
pip install -e .
```

### Usage with Claude Desktop

Add to your Claude Desktop configuration (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "ids-mcp": {
      "command": "python",
      "args": ["-m", "ids_mcp_server"],
      "env": {
        "IDS_LOG_LEVEL": "INFO"
      }
    }
  }
}
```

### Programmatic Usage

```python
from ifctester import ids

# The MCP server handles this automatically via tools
# But you can also use IfcTester directly:

# Create new IDS
my_ids = ids.Ids(title="Project Requirements")

# Add specification
spec = ids.Specification(name="Wall Requirements", ifcVersion=["IFC4"])
spec.applicability.append(ids.Entity(name="IFCWALL"))

requirement = ids.Property(
    baseName="FireRating",
    propertySet="Pset_WallCommon",
    cardinality="required"
)
spec.requirements.append(requirement)

my_ids.specifications.append(spec)

# Export to XML
my_ids.to_xml("requirements.ids")
```

## Available MCP Tools

### Document Management

- **create_ids** - Create new IDS document
- **load_ids** - Load existing IDS from file or XML string
- **export_ids** - Export IDS to XML with validation
- **get_ids_info** - Get document structure and metadata

### Specification Management

- **add_specification** - Add specification with IFC version and cardinality

### Facet Management

#### Basic Facets
- **add_entity_facet** - Add IFC entity type filter (e.g., IFCWALL)
- **add_property_facet** - Add property requirements
- **add_attribute_facet** - Add IFC attribute requirements

#### Advanced Facets
- **add_classification_facet** - Add classification requirements
- **add_material_facet** - Add material requirements
- **add_partof_facet** - Add spatial relationship requirements

### Restriction Management

- **add_enumeration_restriction** - Constrain to list of valid values
- **add_pattern_restriction** - Constrain with regex pattern
- **add_bounds_restriction** - Constrain numeric ranges
- **add_length_restriction** - Constrain string length

### Validation

- **validate_ids** - Validate IDS document against XSD schema
- **validate_ifc_model** - Validate IFC model against IDS (bonus feature)

## Early Validation & Constraint Checking

The MCP server includes **early validation** to catch IDS 1.0 schema violations immediately when tools are called, rather than waiting until export time. This provides AI agents with clear, actionable error messages.

### IDS 1.0 Schema Constraints

#### 1. Single Entity Facet per Applicability

**Constraint**: IDS 1.0 allows only ONE entity facet per specification's applicability section.

**Early Validation**: The `add_entity_facet` tool validates this constraint before adding the facet:

```python
# ✅ CORRECT: First entity facet
add_entity_facet(spec_id="S1", location="applicability", entity_name="IFCWALL")

# ❌ INCORRECT: Second entity facet raises ToolError immediately
add_entity_facet(spec_id="S1", location="applicability", entity_name="IFCDOOR")
# Error: "IDS 1.0 XSD constraint violation: Only ONE entity facet is allowed..."
```

**Workaround**: Create separate specifications for each entity type:
```python
# Specification 1: Walls
add_specification(name="Wall Requirements", ifc_versions=["IFC4"], identifier="S1")
add_entity_facet(spec_id="S1", location="applicability", entity_name="IFCWALL")

# Specification 2: Doors
add_specification(name="Door Requirements", ifc_versions=["IFC4"], identifier="S2")
add_entity_facet(spec_id="S2", location="applicability", entity_name="IFCDOOR")
```

#### 2. Property Set Required for Property Facets

**Constraint**: IfcTester requires `property_set` parameter for valid IDS export.

**Early Validation**: The `add_property_facet` tool validates this requirement before adding the facet:

```python
# ❌ INCORRECT: Missing property_set raises ToolError immediately
add_property_facet(
    spec_id="S1",
    location="requirements",
    property_name="FireRating"
)
# Error: "Property facet validation error: 'property_set' parameter is required..."

# ✅ CORRECT: Include property_set parameter
add_property_facet(
    spec_id="S1",
    location="requirements",
    property_name="FireRating",
    property_set="Pset_WallCommon"
)
```

**Common Property Sets**:
- `Pset_WallCommon` - Wall properties
- `Pset_DoorCommon` - Door properties
- `Pset_WindowCommon` - Window properties
- `Pset_SpaceCommon` - Space properties
- `Pset_Common` - Custom/generic properties

### Benefits of Early Validation

1. **Immediate Feedback** - Errors caught at tool invocation, not export time
2. **Clear Error Messages** - Includes workarounds and examples
3. **Prevents Invalid States** - IDS documents stay valid throughout creation
4. **Better AI Agent Experience** - Agents receive actionable guidance

See [CLAUDE.md](./CLAUDE.md) for detailed documentation on IDS 1.0 constraints.

## Architecture

```
┌─────────────────────────────────────────────┐
│           AI Agent (Claude, GPT)             │
└────────────────────┬────────────────────────┘
                     │ MCP Protocol
┌────────────────────▼────────────────────────┐
│            FastMCP Server                    │
│  ┌──────────────────────────────────────┐   │
│  │     MCP Tools (15+ tools)            │   │
│  └───────────────┬──────────────────────┘   │
│  ┌───────────────▼──────────────────────┐   │
│  │     Session Manager (Context)        │   │
│  └───────────────┬──────────────────────┘   │
│  ┌───────────────▼──────────────────────┐   │
│  │  IfcTester Integration (IDS Engine)  │   │
│  └──────────────────────────────────────┘   │
└─────────────────────────────────────────────┘
                     │
                     ▼
        IDS XML File (100% XSD compliant)
```

## Development

### Test-Driven Development

This project strictly follows TDD methodology:

```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=src/ids_mcp_server --cov-report=html

# Run specific test category
pytest tests/unit/ -v        # Unit tests
pytest tests/integration/ -v  # Integration tests
pytest tests/validation/ -v   # XSD validation tests

# Must maintain 95%+ coverage
pytest tests/ --cov-fail-under=95
```

### TDD Workflow (Red-Green-Refactor)

1. **RED** - Write failing test
2. **GREEN** - Implement minimum code to pass
3. **REFACTOR** - Improve code quality

Example:

```python
# RED: Write failing test
def test_create_specification():
    result = add_specification(name="Test", ifc_versions=["IFC4"])
    assert result["status"] == "success"

# GREEN: Implement
def add_specification(name, ifc_versions):
    return {"status": "success"}

# REFACTOR: Improve (keep tests passing)
```

### Code Quality

```bash
# Format code
black src/ tests/

# Lint code
ruff check src/ tests/

# Type checking (optional)
mypy src/
```

## Project Structure

```
ifc-ids-mcp/
├── src/
│   └── ids_mcp_server/
│       ├── __init__.py
│       ├── __main__.py
│       ├── server.py          # FastMCP server
│       ├── config.py          # Configuration
│       ├── version.py         # Version management
│       ├── session/           # Session management
│       │   ├── manager.py
│       │   ├── storage.py
│       │   ├── cleanup.py
│       │   └── models.py      # Session data models
│       └── tools/             # MCP tools (17 total)
│           ├── document.py
│           ├── specification.py
│           ├── facets.py
│           ├── restrictions.py    # Phase 007
│           ├── validation.py      # Phase 008
│           └── validators.py      # Early validation helpers
├── tests/                     # 168 tests, 94% coverage
│   ├── unit/                  # Unit tests
│   ├── component/             # Component tests
│   ├── integration/           # Integration tests
│   └── validation/            # XSD compliance tests
│       └── fixtures/          # Test fixtures
├── samples/                   # Sample IDS/IFC files
│   ├── wall_fire_rating.ids
│   └── walls-fire-rating.ifc
├── specs/                     # Implementation plans (PRDs)
├── .mcp.json                  # MCP server configuration
├── .coveragerc                # Coverage configuration
├── constitution.md            # Project principles
├── DESIGN_SPECIFICATION.md    # Technical specification
├── CLAUDE.md                  # AI agent guide
├── pyproject.toml
├── pytest.ini
└── README.md
```

## Constitution Principles

This project follows 6 non-negotiable principles:

1. **100% IDS Schema Compliance** - All exports validate against XSD
2. **Test-Driven Development** - 95%+ coverage, tests before code
3. **IfcTester Integration First** - No custom XML generation
4. **Deterministic Generation** - Identical input = identical output
5. **FastMCP Context-Based Sessions** - Automatic session management
6. **Python Best Practices** - Type hints, PEP 8, modern Python

See [constitution.md](./constitution.md) for full details.

## Documentation

- **[Constitution](./constitution.md)** - Non-negotiable principles
- **[Design Specification](./DESIGN_SPECIFICATION.md)** - Complete technical design
- **[AI Agent Guide](./CLAUDE.md)** - Guide for AI agents working on this project
- **[Implementation Plans](./specs/)** - Phase-by-phase PRDs

## Dependencies

### Core
- **fastmcp** - MCP server framework
- **ifctester** - IDS authoring and validation (from IfcOpenShell)
- **pydantic** - Data validation

### Development
- **pytest** - Testing framework
- **pytest-asyncio** - Async test support
- **pytest-cov** - Coverage reporting
- **black** - Code formatting
- **ruff** - Linting

## References

- **IDS Standard**: https://www.buildingsmart.org/standards/bsi-standards/information-delivery-specification-ids/
- **IDS XSD Schema**: https://standards.buildingsmart.org/IDS/1.0/ids.xsd
- **IfcTester Docs**: https://docs.ifcopenshell.org/ifctester.html
- **FastMCP**: https://gofastmcp.com/
- **buildingSMART**: https://www.buildingsmart.org/

## License

MIT License - see [LICENSE](./LICENSE) file for details

## Contributing

1. Read [constitution.md](./constitution.md) for project principles
2. Follow TDD methodology (Red-Green-Refactor)
3. Ensure 95%+ test coverage
4. All exports must validate against IDS 1.0 XSD
5. Use IfcTester for all IDS operations

## Support

- **Issues**: https://github.com/Quasar-Consulting-Group/ifc-ids-mcp/issues
- **Discussions**: https://github.com/Quasar-Consulting-Group/ifc-ids-mcp/discussions

---

**Status**: ✅ Implementation Complete | 94% Test Coverage | 17 MCP Tools | 168 Tests | Early Validation

Built with ❤️ using [IfcOpenShell](https://ifcopenshell.org/) and [FastMCP](https://gofastmcp.com/)