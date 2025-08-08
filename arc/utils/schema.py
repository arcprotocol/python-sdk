"""
ARC Schema Utilities

Provides runtime access to the ARC protocol schema
for validation, documentation, and tooling purposes.
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List

try:
    import yaml
    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False


logger = logging.getLogger(__name__)


def get_package_root() -> Path:
    """Get the root directory of the arc package"""
    return Path(__file__).parent.parent


def get_schema_path() -> Path:
    """Get the path to the ARC schema file"""
    return get_package_root() / "schemas" / "arc_schema.yaml"


def load_arc_schema() -> Dict[str, Any]:
    """
    Load the ARC schema from the package.
    
    Returns:
        Dictionary containing the ARC schema
        
    Raises:
        FileNotFoundError: If schema file is not found
        ImportError: If PyYAML is not available
        ValueError: If schema cannot be parsed
    """
    if not YAML_AVAILABLE:
        raise ImportError(
            "PyYAML is required to load the ARC schema. "
            "Install it with: pip install PyYAML"
        )
    
    schema_path = get_schema_path()
    
    if not schema_path.exists():
        raise FileNotFoundError(f"ARC schema not found at: {schema_path}")
    
    try:
        with open(schema_path, 'r', encoding='utf-8') as f:
            schema = yaml.safe_load(f)
        
        logger.debug(f"Loaded ARC schema from: {schema_path}")
        return schema
        
    except yaml.YAMLError as e:
        raise ValueError(f"Failed to parse ARC schema: {e}")
    except Exception as e:
        raise ValueError(f"Failed to load ARC schema: {e}")


def get_schema_version() -> Optional[str]:
    """
    Get the version of the ARC schema.
    
    Returns:
        Schema version string or None if not found
    """
    try:
        schema = load_arc_schema()
        return schema.get("info", {}).get("version")
    except Exception as e:
        logger.warning(f"Failed to get schema version: {e}")
        return None


def get_schema_info() -> Dict[str, Any]:
    """
    Get basic information about the ARC schema.
    
    Returns:
        Dictionary with schema metadata
    """
    try:
        schema = load_arc_schema()
        info = schema.get("info", {})
        
        return {
            "title": info.get("title", "Unknown"),
            "version": info.get("version", "Unknown"),
            "description": info.get("description", ""),
            "schema_path": str(get_schema_path()),
            "available": True
        }
    except Exception as e:
        logger.warning(f"Failed to get schema info: {e}")
        return {
            "title": "ARC Protocol Schema",
            "version": "Unknown",
            "description": "",
            "schema_path": str(get_schema_path()),
            "available": False,
            "error": str(e)
        }


def get_available_methods() -> Dict[str, Dict[str, Any]]:
    """
    Get list of available ARC methods from the schema.
    
    Returns:
        Dictionary of method names mapped to their documentation
    """
    methods = {}
    
    try:
        schema = load_arc_schema()
        
        # Look for methods in the schema
        for path, path_item in schema.get("paths", {}).items():
            # Check if this is an ARC method
            if path == "/arc" and "post" in path_item:
                post_op = path_item["post"]
                request_body = post_op.get("requestBody", {})
                content = request_body.get("content", {})
                schema_ref = content.get("application/arc+json", {}).get("schema", {})
                
                # Extract method properties from components
                if "$ref" in schema_ref:
                    ref_parts = schema_ref["$ref"].split("/")
                    ref_name = ref_parts[-1]
                    component = schema.get("components", {}).get("schemas", {}).get(ref_name, {})
                    
                    # Extract method information
                    methods_enum = component.get("properties", {}).get("method", {}).get("enum", [])
                    
                    # Get method documentation
                    for method_name in methods_enum:
                        # Try to find detailed documentation
                        method_docs = {
                            "name": method_name,
                            "description": f"ARC method: {method_name}",
                            "params": {},
                        }
                        
                        # Try to find method parameters
                        params_component = schema.get("components", {}).get("schemas", {}).get(f"{method_name.replace('.', '')}Params", {})
                        if params_component:
                            method_docs["description"] = params_component.get("description", method_docs["description"])
                            
                            # Extract parameter properties
                            for param_name, param_schema in params_component.get("properties", {}).items():
                                param_info = {
                                    "type": param_schema.get("type", "object"),
                                    "description": param_schema.get("description", ""),
                                    "required": param_name in params_component.get("required", [])
                                }
                                method_docs["params"][param_name] = param_info
                        
                        methods[method_name] = method_docs
        
        return methods
        
    except Exception as e:
        logger.warning(f"Failed to get available methods: {e}")
        return {}


def get_method_documentation(method_name: str) -> Dict[str, Any]:
    """
    Get documentation for a specific ARC method.
    
    Args:
        method_name: Name of the ARC method (e.g., "task.create")
        
    Returns:
        Dictionary with method documentation
    """
    methods = get_available_methods()
    return methods.get(method_name, {
        "name": method_name,
        "description": f"Unknown method: {method_name}",
        "params": {}
    })


def validate_against_schema(data: Dict[str, Any], schema_name: str) -> bool:
    """
    Validate data against a schema component.
    
    Args:
        data: Data to validate
        schema_name: Name of the schema component
        
    Returns:
        True if valid, False otherwise
    """
    try:
        # Try to import jsonschema if available
        import jsonschema
        
        schema = load_arc_schema()
        component_schema = schema.get("components", {}).get("schemas", {}).get(schema_name)
        
        if not component_schema:
            logger.warning(f"Schema component not found: {schema_name}")
            return False
        
        # Expand schema references
        def resolve_refs(schema_obj, base_schema):
            if isinstance(schema_obj, dict):
                if "$ref" in schema_obj:
                    ref = schema_obj["$ref"]
                    if ref.startswith("#/components/schemas/"):
                        ref_name = ref.split("/")[-1]
                        return resolve_refs(base_schema["components"]["schemas"][ref_name], base_schema)
                    
                resolved_obj = {}
                for k, v in schema_obj.items():
                    if k == "$ref":
                        continue
                    resolved_obj[k] = resolve_refs(v, base_schema)
                return resolved_obj
            elif isinstance(schema_obj, list):
                return [resolve_refs(item, base_schema) for item in schema_obj]
            else:
                return schema_obj
        
        resolved_schema = resolve_refs(component_schema, schema)
        
        # Validate
        jsonschema.validate(data, resolved_schema)
        return True
        
    except ImportError:
        logger.warning("jsonschema package not available. Install it with: pip install jsonschema")
        return True  # Skip validation
    except Exception as e:
        logger.warning(f"Validation failed: {e}")
        return False


def export_schema_as_json(output_path: Optional[str] = None) -> str:
    """
    Export the ARC schema as JSON.
    
    Args:
        output_path: Optional path to write the JSON file
        
    Returns:
        Path to the exported file or JSON string if no path provided
    """
    try:
        schema = load_arc_schema()
        json_str = json.dumps(schema, indent=2)
        
        if output_path:
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(json_str)
            logger.info(f"Exported ARC schema to: {output_path}")
            return output_path
        else:
            return json_str
            
    except Exception as e:
        logger.error(f"Failed to export schema: {e}")
        raise


def get_model_schemas() -> Dict[str, Any]:
    """
    Get all model schemas from the ARC schema.
    
    Returns:
        Dictionary mapping model names to their schemas
    """
    try:
        schema = load_arc_schema()
        return schema.get("components", {}).get("schemas", {})
    except Exception as e:
        logger.warning(f"Failed to get model schemas: {e}")
        return {}


def list_method_categories() -> Dict[str, List[str]]:
    """
    Group ARC methods by category.
    
    Returns:
        Dictionary mapping categories to method names
    """
    methods = get_available_methods()
    categories = {}
    
    for method_name in methods:
        category = method_name.split('.')[0]
        if category not in categories:
            categories[category] = []
        categories[category].append(method_name)
    
    return categories


def get_error_codes() -> Dict[str, Dict[str, Any]]:
    """
    Get all ARC error codes from the schema.
    
    Returns:
        Dictionary mapping error code ranges to their documentation
    """
    try:
        schema = load_arc_schema()
        error_components = schema.get("components", {}).get("schemas", {})
        
        error_codes = {}
        for name, component in error_components.items():
            if name.endswith("Error") and "properties" in component:
                # Check if this has an error code property
                props = component.get("properties", {})
                if "code" in props:
                    code_info = props["code"]
                    if "enum" in code_info:
                        code = code_info["enum"][0]
                        error_codes[code] = {
                            "name": name,
                            "code": code,
                            "description": component.get("description", f"Error code {code}")
                        }
        
        return error_codes
    except Exception as e:
        logger.warning(f"Failed to get error codes: {e}")
        return {}


def print_schema_info():
    """Print information about the ARC schema to the console."""
    info = get_schema_info()
    print(f"ARC Protocol Schema:")
    print(f"  Title: {info['title']}")
    print(f"  Version: {info['version']}")
    print(f"  Path: {info['schema_path']}")
    print(f"  Available: {info['available']}")
    if not info['available']:
        print(f"  Error: {info.get('error', 'Unknown')}")


def print_available_methods():
    """Print available ARC methods to the console."""
    categories = list_method_categories()
    
    print("ARC Protocol Methods:")
    for category, methods in categories.items():
        print(f"\n{category.upper()} METHODS:")
        for method in sorted(methods):
            docs = get_method_documentation(method)
            print(f"  {method} - {docs.get('description', '')}")


if __name__ == "__main__":
    # Simple command line interface
    print_schema_info()
    print_available_methods()