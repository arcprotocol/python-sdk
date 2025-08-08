#!/usr/bin/env python3
"""
Script to update ARC schema terminology from 'stream' to 'chat'
"""

import os
import sys
import yaml

try:
    import yaml
except ImportError:
    print("PyYAML is required. Please install it with 'pip install PyYAML'")
    sys.exit(1)

def update_schema():
    # Path to schema file
    schema_path = os.path.join(os.path.dirname(__file__), 'arc_schema.yaml')
    
    # Load schema
    with open(schema_path, 'r') as f:
        schema = yaml.safe_load(f)
    
    # Update paths
    # 1. Rename /arc/stream.* paths to /arc/chat.*
    new_paths = {}
    for path, data in schema.get('paths', {}).items():
        new_path = path
        
        # Rename stream to chat in path
        if '/stream.' in path:
            new_path = path.replace('/stream.', '/chat.')
        
        # Update path data
        new_paths[new_path] = data
        
        # Update tags and operation IDs
        if 'post' in data:
            post_data = data['post']
            
            # Update tags
            tags = post_data.get('tags', [])
            for i, tag in enumerate(tags):
                if tag == 'Stream Methods':
                    tags[i] = 'Chat Methods'
            
            # Update operationId
            if 'operationId' in post_data:
                if post_data['operationId'].startswith('stream'):
                    post_data['operationId'] = post_data['operationId'].replace('stream', 'chat')
            
            # Update description
            if 'description' in post_data:
                post_data['description'] = post_data['description'].replace('stream', 'chat').replace('Stream', 'Chat')
            
            # Update security scopes
            if 'security' in post_data:
                for sec in post_data.get('security', []):
                    if 'OAuth2' in sec:
                        scopes = sec['OAuth2']
                        for i, scope in enumerate(scopes):
                            if 'arc.stream' in scope:
                                scopes[i] = scope.replace('arc.stream', 'arc.chat')
            
            # Update request body schema
            if 'requestBody' in post_data and 'content' in post_data['requestBody']:
                for content_type, content_data in post_data['requestBody']['content'].items():
                    if 'schema' in content_data:
                        schema_obj = content_data['schema']
                        
                        # Update method enum
                        if 'allOf' in schema_obj:
                            for part in schema_obj['allOf']:
                                if 'properties' in part and 'method' in part['properties']:
                                    method_prop = part['properties']['method']
                                    if 'enum' in method_prop:
                                        for i, method in enumerate(method_prop['enum']):
                                            if 'stream.' in method:
                                                method_prop['enum'][i] = method.replace('stream.', 'chat.')
                                
                                if 'properties' in part and 'params' in part['properties']:
                                    params_prop = part['properties']['params']
                                    if '$ref' in params_prop and 'Stream' in params_prop['$ref']:
                                        params_prop['$ref'] = params_prop['$ref'].replace('Stream', 'Chat')
                    
                    # Update example
                    if 'example' in content_data:
                        example = content_data['example']
                        if 'method' in example and 'stream.' in example['method']:
                            example['method'] = example['method'].replace('stream.', 'chat.')
                        
                        if 'params' in example:
                            params = example['params']
                            if 'streamId' in params:
                                params['chatId'] = params.pop('streamId')
            
            # Update responses
            if 'responses' in post_data:
                for code, response in post_data['responses'].items():
                    if 'description' in response:
                        response['description'] = response['description'].replace('Stream', 'Chat').replace('stream', 'chat')
                    
                    if 'content' in response:
                        for content_type, content_data in response['content'].items():
                            if 'schema' in content_data:
                                schema_obj = content_data['schema']
                                
                                if 'allOf' in schema_obj:
                                    for part in schema_obj['allOf']:
                                        if 'properties' in part and 'result' in part['properties']:
                                            result_prop = part['properties']['result']
                                            if '$ref' in result_prop and 'Stream' in result_prop['$ref']:
                                                result_prop['$ref'] = result_prop['$ref'].replace('Stream', 'Chat')
    
    # Replace paths with updated paths
    schema['paths'] = new_paths
    
    # Update components schemas
    components = schema.get('components', {}).get('schemas', {})
    new_components = {}
    
    for name, component in components.items():
        new_name = name
        
        # Rename Stream* components to Chat*
        if name.startswith('Stream'):
            new_name = 'Chat' + name[6:]
        
        new_components[new_name] = component
        
        # Update references within the component
        if 'properties' in component:
            # Make a copy of the keys to avoid modification during iteration
            prop_names = list(component['properties'].keys())
            for prop_name in prop_names:
                prop = component['properties'][prop_name]
                
                if prop_name == 'streamId':
                    # Rename streamId to chatId
                    component['properties']['chatId'] = component['properties'].pop('streamId')
                    if 'description' in prop:
                        prop['description'] = prop['description'].replace('stream', 'chat').replace('Stream', 'Chat')
                    if 'example' in prop and 'stream-' in prop['example']:
                        prop['example'] = prop['example'].replace('stream-', 'chat-')
                
                # Update descriptions
                if 'description' in prop:
                    prop['description'] = prop['description'].replace('stream', 'chat').replace('Stream', 'Chat')
                
                # Update references
                if '$ref' in prop and 'Stream' in prop['$ref']:
                    prop['$ref'] = prop['$ref'].replace('Stream', 'Chat')
                
                # Update enum values
                if prop_name == 'type' and 'enum' in prop:
                    for i, val in enumerate(prop['enum']):
                        if val == 'stream':
                            prop['enum'][i] = 'chat'
        
        # Update required fields
        if 'required' in component:
            required = component['required']
            for i, field in enumerate(required):
                if field == 'streamId':
                    required[i] = 'chatId'
                elif field == 'stream':
                    required[i] = 'chat'
    
    # Replace components with updated components
    schema['components']['schemas'] = new_components
    
    # Update security scopes
    if 'securitySchemes' in schema['components']:
        for scheme_name, scheme in schema['components']['securitySchemes'].items():
            if 'flows' in scheme:
                for flow_name, flow in scheme['flows'].items():
                    if 'scopes' in flow:
                        scopes = flow['scopes']
                        new_scopes = {}
                        for scope, desc in scopes.items():
                            if 'arc.stream' in scope:
                                new_scope = scope.replace('arc.stream', 'arc.chat')
                                new_scopes[new_scope] = desc.replace('stream', 'chat').replace('Stream', 'Chat')
                            else:
                                new_scopes[scope] = desc
                        flow['scopes'] = new_scopes
    
    # Update tags
    for i, tag in enumerate(schema.get('tags', [])):
        if tag['name'] == 'Stream Methods':
            tag['name'] = 'Chat Methods'
            tag['description'] = tag['description'].replace('stream', 'chat').replace('Stream', 'Chat')
    
    # Save updated schema
    with open(schema_path, 'w') as f:
        yaml.dump(schema, f, sort_keys=False, default_flow_style=False)
    
    print(f"Updated schema at {schema_path}")

if __name__ == "__main__":
    update_schema()