from typing import List
from pathlib import Path
import ast
from return_py_object_info import get_object_dependencies

def move_objects(object_names: List[str], source_file_path: str, dest_file_path: str, remove_from_source: bool = False, position: str = None, handle_conflicts: str = 'overwrite') -> None:
    try:
        # Resolve the file paths
        source_file_path = Path(source_file_path).resolve()
        dest_file_path = Path(dest_file_path).resolve()

        # Read the contents of the source file
        with open(source_file_path, 'r') as source_file:
            source_code = source_file.read()

        # Parse the source code into an AST
        source_tree = ast.parse(source_code)

        # Find the objects (functions and classes) to move and their import statements
        object_nodes = []
        import_nodes = []
        for node in ast.walk(source_tree):
            if (isinstance(node, ast.FunctionDef) or isinstance(node, ast.ClassDef)) and node.name in object_names:
                object_nodes.append(node)
                # Find import statements used in the object
                for child_node in ast.walk(node):
                    if isinstance(child_node, ast.Import) or isinstance(child_node, ast.ImportFrom):
                        import_nodes.append(child_node)

        if len(object_nodes) != len(object_names):
            missing_objects = set(object_names) - set(node.name for node in object_nodes)
            raise ValueError(f"Objects {missing_objects} not found in {source_file_path}.")

        # Get the unique dependencies of the objects
        unique_dependencies = get_object_dependencies(source_file_path, object_names)

        # Read the contents of the destination file (if it exists)
        dest_code = ''
        if dest_file_path.is_file():
            with open(dest_file_path, 'r') as dest_file:
                dest_code = dest_file.read()

        # Parse the destination code into an AST
        dest_tree = ast.parse(dest_code)

        # Process each object to move
        for object_node in object_nodes:
            object_name = object_node.name

            # Check if the object already exists in the destination file
            object_exists = any((isinstance(node, ast.FunctionDef) or isinstance(node, ast.ClassDef)) and node.name == object_name for node in dest_tree.body)
            if object_exists:
                if handle_conflicts == 'rename':
                    # Rename the object to avoid conflicts
                    new_object_name = f"{object_name}_moved"
                    object_node.name = new_object_name
                    print(f"Object '{object_name}' renamed to '{new_object_name}' to avoid conflicts.")
                elif handle_conflicts == 'overwrite':
                    # Remove the existing object from the destination tree
                    dest_tree.body = [node for node in dest_tree.body if not ((isinstance(node, ast.FunctionDef) or isinstance(node, ast.ClassDef)) and node.name == object_name)]
                elif handle_conflicts == 'skip':
                    print(f"Object '{object_name}' already exists in {dest_file_path}. Skipping...")
                    continue
                else:
                    raise ValueError(f"Invalid value for handle_conflicts: {handle_conflicts}")

            # Add the necessary import statements to the destination tree
            for import_node in import_nodes:
                if not any(ast.unparse(node) == ast.unparse(import_node) for node in dest_tree.body):
                    dest_tree.body.insert(0, import_node)

            # Add import statements for the unique dependencies
            for dependency in unique_dependencies:
                import_stmt = ast.Import(names=[ast.alias(name=dependency)])
                if not any(ast.unparse(node) == ast.unparse(import_stmt) for node in dest_tree.body):
                    dest_tree.body.insert(0, import_stmt)

            # Determine the position to add the object node
            if position is None or position == 'bottom':
                # Add the object node to the end of the destination tree
                dest_tree.body.append(object_node)
            elif position == 'top':
                # Add the object node to the beginning of the destination tree
                dest_tree.body.insert(0, object_node)
            else:
                # Find the specified function or class in the destination tree
                target_node = None
                for node in dest_tree.body:
                    if (isinstance(node, ast.FunctionDef) or isinstance(node, ast.ClassDef)) and node.name == position:
                        target_node = node
                        break

                if target_node is None:
                    print(f"Target '{position}' not found in {dest_file_path}. Adding object at the end.")
                    dest_tree.body.append(object_node)
                else:
                    # Add the object node after the target node
                    target_index = dest_tree.body.index(target_node)
                    dest_tree.body.insert(target_index + 1, object_node)

            if remove_from_source:
                # Remove the object node from the source tree
                source_tree.body.remove(object_node)

        # Generate the modified destination code
        modified_dest_code = ast.unparse(dest_tree)

        # Write the modified destination code to the destination file
        with open(dest_file_path, 'w') as dest_file:
            dest_file.write(modified_dest_code)

        if remove_from_source:
            # Generate the modified source code
            modified_source_code = ast.unparse(source_tree)

            # Write the modified source code back to the source file
            with open(source_file_path, 'w') as source_file:
                source_file.write(modified_source_code)

        print(f"Objects {object_names} moved successfully from {source_file_path} to {dest_file_path}.")

    except FileNotFoundError as e:
        raise FileNotFoundError(f"File not found: {e.filename}") from e
    except SyntaxError as e:
        raise SyntaxError(f"Invalid syntax in the source file: {source_file_path}") from None
    except Exception as e:
        raise Exception(f"An error occurred: {str(e)}") from None