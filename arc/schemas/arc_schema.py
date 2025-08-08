"""
ARC Schema Module

Loads and processes the ARC protocol schema for use in validation,
model generation, and documentation.
"""

import json
import os
from pathlib import Path
from typing import Dict, Any, List, Optional, Union, Tuple

try:
    import yaml
    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False


class ARCSchema:
    """
    ARC protocol schema loader and processor.
    
    Loads the OpenAPI schema for the ARC protocol and provides
    access to schema components, paths, and definitions.
    """
    
    def __init__(self, schema_path: Optional[str] = None):
        """
        Initialize schema loader.
        
        Args:
            schema_path: Optional path to schema file (default: package schema)
            
        Raises:
            ImportError: If PyYAML is not available
            FileNotFoundError: If schema file is not found
            ValueError: If schema cannot be parsed
        """
        if not YAML_AVAILABLE:
            raise ImportError(
                "PyYAML is required to load the ARC schema. "
                "Install it with: pip install PyYAML"
            )
        
        # Use specified path or find package schema
        if schema_path:
            self.schema_path = Path(schema_path)
        else:
            self.schema_path = self._find_schema_path()
        
        # Load schema
        self.schema = self._load_schema()
        
        # Initialize caches
        self._method_params_cache = {}
        self._method_response_cache = {}
        self._components_cache = {}
    
    def _find_schema_path(self) -> Path:
        """
        Find the path to the ARC schema file.
        
        Returns:
            Path to schema file
            
        Raises:
            FileNotFoundError: If schema file cannot be found
        """
        # Look in the current directory
        current_dir = Path.cwd()
        
        # Try current directory first
        if (current_dir / "arc_schema.yaml").exists():
            return current_dir / "arc_schema.yaml"
        
        # Try package directory
        package_dir = Path(__file__).parent
        if (package_dir / "arc_schema.yaml").exists():
            return package_dir / "arc_schema.yaml"
        
        # Try one level up from package directory
        if (package_dir.parent.parent / "arc_schema.yaml").exists():
            return package_dir.parent.parent / "arc_schema.yaml"
        
        raise FileNotFoundError(
            "ARC schema file not found. Please specify the path to the schema file."
        )
    
    def _load_schema(self) -> Dict[str, Any]:
        """
        Load the ARC schema from YAML file.
        
        Returns:
            Schema as dictionary
            
        Raises:
            FileNotFoundError: If schema file is not found
            ValueError: If schema cannot be parsed
        """
        if not self.schema_path.exists():
            raise FileNotFoundError(f"Schema file not found: {self.schema_path}")
        
        try:
            with open(self.schema_path, 'r', encoding='utf-8') as f:
                schema = yaml.safe_load(f)
            return schema
        except yaml.YAMLError as e:
            raise ValueError(f"Failed to parse schema: {e}")
        except Exception as e:
            raise ValueError(f"Failed to load schema: {e}")
    
    def export_json(self, output_path: Optional[str] = None) -> str:
        """
        Export schema as JSON.
        
        Args:
            output_path: Optional path to write JSON file
            
        Returns:
            Path to JSON file or JSON string
        """
        json_str = json.dumps(self.schema, indent=2)
        
        if output_path:
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(json_str)
            return output_path
        else:
            return json_str
    
    def get_info(self) -> Dict[str, Any]:
        """
        Get schema info section.
        
        Returns:
            Schema info object
        """
        return self.schema.get("info", {})
    
    def get_version(self) -> str:
        """
        Get protocol version.
        
        Returns:
            Protocol version string
        """
        return self.schema.get("info", {}).get("version", "unknown")
    
    def get_methods(self) -> List[str]:
        """
        Get list of all ARC methods.
        
        Returns:
            List of method names
        """
        methods = []
        
        # Extract method names from request bodies
        for path, path_item in self.schema.get("paths", {}).items():
            if "post" in path_item:
                post_op = path_item["post"]
                request_body = post_op.get("requestBody", {})
                content = request_body.get("content", {})
                schema_ref = content.get("application/arc+json", {}).get("schema", {})
                
                # Extract method from enum
                properties = schema_ref.get("properties", {})
                method_prop = properties.get("method", {})
                if "enum" in method_prop:
                    methods.extend(method_prop["enum"])
        
        return methods
    
    def get_method_params_schema(self, method: str) -> Optional[Dict[str, Any]]:
        """
        Get params schema for a specific method.
        
        Args:
            method: Method name (e.g., "task.create")
            
        Returns:
            Params schema or None if not found
        """
        # Check cache first
        if method in self._method_params_cache:
            return self._method_params_cache[method]
        
        # Clean method name for schema lookup
        clean_method = method.replace(".", "")
        param_name = f"{clean_method}Params"
        
        # Look for component schema
        components = self.schema.get("components", {}).get("schemas", {})
        if param_name in components:
            self._method_params_cache[method] = components[param_name]
            return components[param_name]
        
        # Try paths
        for path, path_item in self.schema.get("paths", {}).items():
            if path.endswith(f"/{method}"):
                if "post" in path_item:
                    post_op = path_item["post"]
                    request_body = post_op.get("requestBody", {})
                    content = request_body.get("content", {})
                    schema_ref = content.get("application/arc+json", {}).get("schema", {})
                    
                    # Find params reference
                    for prop in schema_ref.get("allOf", []):
                        if "properties" in prop:
                            params_ref = prop.get("properties", {}).get("params", {})
                            if "$ref" in params_ref:
                                ref = params_ref["$ref"].split("/")[-1]
                                if ref in components:
                                    self._method_params_cache[method] = components[ref]
                                    return components[ref]
        
        return None
    
    def get_method_response_schema(self, method: str) -> Optional[Dict[str, Any]]:
        """
        Get response schema for a specific method.
        
        Args:
            method: Method name (e.g., "task.create")
            
        Returns:
            Response schema or None if not found
        """
        # Check cache first
        if method in self._method_response_cache:
            return self._method_response_cache[method]
        
        # Look in paths
        for path, path_item in self.schema.get("paths", {}).items():
            if path.endswith(f"/{method}"):
                if "post" in path_item:
                    post_op = path_item["post"]
                    responses = post_op.get("responses", {})
                    success_response = responses.get("200", {})
                    content = success_response.get("content", {})
                    schema_ref = content.get("application/arc+json", {}).get("schema", {})
                    
                    # Find result reference
                    for prop in schema_ref.get("allOf", []):
                        if "properties" in prop:
                            result_ref = prop.get("properties", {}).get("result", {})
                            
                            if "$ref" in result_ref:
                                components = self.schema.get("components", {}).get("schemas", {})
                                ref = result_ref["$ref"].split("/")[-1]
                                if ref in components:
                                    self._method_response_cache[method] = components[ref]
                                    return components[ref]
        
        return None
    
    def get_component_schema(self, name: str) -> Optional[Dict[str, Any]]:
        """
        Get a component schema by name.
        
        Args:
            name: Component name
            
        Returns:
            Component schema or None if not found
        """
        # Check cache first
        if name in self._components_cache:
            return self._components_cache[name]
        
        # Look in components
        components = self.schema.get("components", {}).get("schemas", {})
        if name in components:
            self._components_cache[name] = components[name]
            return components[name]
        
        return None
    
    def get_all_components(self) -> Dict[str, Any]:
        """
        Get all component schemas.
        
        Returns:
            Dictionary of all component schemas
        """
        return self.schema.get("components", {}).get("schemas", {})
    
    def get_request_schema(self) -> Dict[str, Any]:
        """
        Get the ARC request schema.
        
        Returns:
            ARC request schema
        """
        return self.get_component_schema("ARCRequest") or {}
    
    def get_response_schema(self) -> Dict[str, Any]:
        """
        Get the ARC response schema.
        
        Returns:
            ARC response schema
        """
        return self.get_component_schema("ARCResponse") or {}
    
    def get_error_codes(self) -> Dict[int, Dict[str, Any]]:
        """
        Get all error codes defined in the schema.
        
        Returns:
            Dictionary mapping error codes to their descriptions
        """
        error_codes = {}
        
        # Extract from schema
        for name, component in self.get_all_components().items():
            if name.endswith("Error") and "properties" in component:
                props = component.get("properties", {})
                if "code" in props and "enum" in props["code"]:
                    for code in props["code"]["enum"]:
                        error_codes[code] = {
                            "name": name,
                            "code": code,
                            "description": component.get("description", "")
                        }
        
        return error_codes
    
    def get_required_scopes(self, method: str) -> List[str]:
        """
        Get required OAuth2 scopes for a method.
        
        Args:
            method: Method name
            
        Returns:
            List of required scope strings
        """
        scopes = []
        
        # Look in paths
        for path, path_item in self.schema.get("paths", {}).items():
            if path.endswith(f"/{method}"):
                if "post" in path_item:
                    post_op = path_item["post"]
                    security = post_op.get("security", [])
                    
                    for sec_req in security:
                        if "OAuth2" in sec_req:
                            scopes.extend(sec_req["OAuth2"])
        
        return scopes


# Create singleton instance
_schema_instance = None


def get_schema() -> ARCSchema:
    """
    Get the singleton schema instance.
    
    Returns:
        ARCSchema instance
    """
    global _schema_instance
    
    if _schema_instance is None:
        try:
            _schema_instance = ARCSchema()
        except (ImportError, FileNotFoundError, ValueError) as e:
            import logging
            logging.warning(f"Failed to load ARC schema: {e}")
            _schema_instance = None
    
    return _schema_instance
