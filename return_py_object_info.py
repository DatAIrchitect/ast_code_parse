import inspect
import ast
import sys
import re
from typing import Tuple, List,Dict, Union, Any, Optional, Literal, Type, Callable
from pathlib import Path
import traceback
from returns.result import Result, Success, Failure
from functools import wraps

class ExceptionWithDict(Exception):
    def __init__(self, exception_dict: Dict[str, Any], original_exception: Exception):
        self.exception_dict = exception_dict
        self.original_exception = original_exception

def exception_handler(func: Callable) -> Callable:
    """
    Decorator that captures exceptions, returns a Result object, and raises a custom exception.

    Args:
        func: The function to be decorated.

    Returns:
        A decorated function that captures exceptions, returns a Result object, and raises a custom exception.
    """
    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Result[Any, Dict[str, Any]]:
        try:
            result = func(*args, **kwargs)
            return Success(result)
        except Exception as e:
            exc_type, exc_value, exc_traceback = sys.exc_info()
            traceback_details = traceback.extract_tb(exc_traceback)

            exception_dict = {
                "func_name": func.__name__,
                "exception_type": exc_type.__name__,
                "exception_message": str(exc_value),
                "traceback": [
                    {
                        "filename": detail.filename,
                        "line_number": detail.lineno,
                        "function": detail.name,
                        "code": detail.line,
                    }
                    for detail in traceback_details
                ],
            }

            # Raise the custom exception with the exception dictionary and original exception
            raise ExceptionWithDict(exception_dict, e)

    return wrapper

def missing_funcs_in_get_meta_data(filepath: str = None) -> Dict[str, List[str]]:
    """
    Compare the functions and classes obtained from get_meta_data and get_functions_and_classes_regex.
    Return a dictionary with the missing functions and classes in each method.

    Args:
        filepath (str, optional): The path to the file. Defaults to None.

    Returns:
        Dict[str, List[str]]: A dictionary with keys 'missing_in_get_meta_data' and 'missing_in_regex',
                              containing the missing functions and classes in each method.
    """
    # Get the functions and classes using get_meta_data
    meta_data_funcs = set(item['name'] for item in get_meta_data(filepath))

    # Get the functions and classes using get_functions_and_classes_regex
    regex_funcs = set(get_primary_functions_and_classes_regex(filepath))

    # Find the missing functions and classes in each method
    missing_in_meta_data = list(regex_funcs - meta_data_funcs)
    missing_in_regex = list(meta_data_funcs - regex_funcs)

    return {
        'missing_in_get_meta_data': missing_in_meta_data,
        'missing_in_regex': missing_in_regex
    }

def get_primary_functions_and_classes_regex(file_path: str) -> Tuple[List[str], List[str]]:
    """
    Returns the names of primary functions and classes in a Python file using regex.

    Args:
        file_path (str): The path to the Python file.

    Returns:
        tuple: A tuple containing two lists:
            - functions: A list of primary function names.
            - classes: A list of primary class names.
    """
    with open(file_path, "r") as file:
        content = file.read()

    # Regular expression pattern to match primary function and class definitions
    pattern = r"^(?:def|class)\s+(\w+)"

    matches = re.findall(pattern, content, re.MULTILINE)
    functions = []
    classes = []

    for match in matches:
        if match.islower():
            # Function names are typically in lowercase
            functions.append(match)
        else:
            # Class names are typically in PascalCase
            classes.append(match)

    return functions, classes

def get_meta_data(file_path: Union[str, Path], obj_names: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    """
    Get metadata for specified objects in a Python file.

    Args:
        file_path (Union[str, Path]): The path to the Python file.
        obj_names (Optional[List[str]], optional): A list of object names to retrieve metadata for.
            If None, metadata will be retrieved for all user-defined objects in the file. Defaults to None.

    Returns:
        List[Dict[str, Any]]: A list of dictionaries containing metadata for each object.

    Raises:
        FileNotFoundError: If the specified file path does not exist.
        SyntaxError: If the Python file contains syntax errors.
        ImportError: If there are issues importing the module or its dependencies.
    """
    file_path = Path(file_path)
    meta_data_list = []
    all_objects = get_user_defined_objects(file_path)

    if obj_names:
        all_objects = {key: all_objects[key] for key in obj_names if key in all_objects}

    module_name = file_path.stem
    try:
        module = __import__(module_name)
    except ImportError as e:
        raise ImportError(f"Failed to import module '{module_name}': {str(e)}") from e

    for obj_name, obj_type in all_objects.items():
        try:
            obj = getattr(module, obj_name)
        except AttributeError:
            print(f"Object '{obj_name}' not found in the file.")
            continue

        if inspect.ismethod(obj) or inspect.ismethoddescriptor(obj) or inspect.ismemberdescriptor(obj):
            continue

        try:
            meta_data = get_object_metadata(obj, file_path)
            meta_data_list.append(meta_data)
        except Exception as e:
            print(f"Error occurred while processing object {obj}: {str(e)}")

    return meta_data_list


def get_user_defined_objects(file_path: Union[str, Path]) -> Dict[str, str]:
    """
    Get user-defined objects (classes and functions) from a Python file.

    Args:
        file_path (Union[str, Path]): The path to the Python file.

    Returns:
        Dict[str, str]: A dictionary mapping object names to their types (class or function).
    """
    if isinstance(file_path, str):
        file_path = Path(file_path)

    with open(file_path, 'r') as file:
        tree = ast.parse(file.read())

    objects = {}
    for node in ast.walk(tree):
        if isinstance(node, (ast.ClassDef, ast.FunctionDef)):
            objects[node.name] = 'class' if isinstance(node, ast.ClassDef) else 'function'

    module_name = file_path.stem
    module = __import__(module_name)

    filtered_objects = {}
    for obj_name, obj_type in objects.items():
        if hasattr(module, obj_name):
            filtered_objects[obj_name] = obj_type

    return filtered_objects


def get_object_metadata(obj: Any, file_path: Path) -> Dict[str, Any]:
    """
    Get metadata for a specific object.

    Args:
        obj (Any): The object to retrieve metadata for.
        file_path (Path): The path to the Python file containing the object.

    Returns:
        Dict[str, Any]: A dictionary containing metadata for the object.
    """
    meta_data = {}

    # Get the object's name
    meta_data['name'] = obj.__name__

    # Get the object's docstring (if available)
    meta_data['docstring'] = inspect.getdoc(obj)

    meta_data['orig_file'] = str(file_path)

    try:
        source_lines, start_line_number = inspect.getsourcelines(obj)
        end_line_number = start_line_number + len(source_lines) - 1
        meta_data['start_line'] = start_line_number
        meta_data['end_line'] = end_line_number
    except (OSError, TypeError):
        meta_data['start_line'] = None
        meta_data['end_line'] = None

    # Get the object's type (class or function)
    meta_data['type'] = 'class' if inspect.isclass(obj) else 'function'

    # Get the object's module name
    if hasattr(obj, '__module__'):
        meta_data['module'] = obj.__module__
    else:
        meta_data['module'] = None

    # Get the object's source code (if available)
    try:
        meta_data['source_code'] = inspect.getsource(obj)
    except (OSError, TypeError, AttributeError):
        meta_data['source_code'] = None

    # Get the object's attributes (if it's a class)
    if inspect.isclass(obj):
        meta_data['attributes'] = get_class_attributes(obj)

    # Get the object's parameters and return type (if it's a function)
    if inspect.isfunction(obj):
        meta_data['parameters'] = get_function_parameters(obj)
        meta_data['arg_spec'] = inspect.getfullargspec(obj)
        meta_data['signature'] = inspect.signature(obj)
        meta_data['return_type'] = get_function_return_type(obj)

    # Get the object's dependencies
    if meta_data['source_code']:
        meta_data['dependencies'] = get_object_dependencies(obj, meta_data['source_code'])
    else:
        meta_data['dependencies'] = None

    return meta_data


def get_class_attributes(obj: Any) -> Dict[str, str]:
    """
    Get the attributes of a class object.

    Args:
        obj (Any): The class object.

    Returns:
        Dict[str, str]: A dictionary mapping attribute names to their string representations.
    """
    attributes = {}
    for attr_name in dir(obj):
        if not attr_name.startswith('_'):
            attr_value = getattr(obj, attr_name, None)
            if attr_value is not None and not inspect.ismethod(attr_value) and not inspect.isfunction(attr_value):
                attributes[attr_name] = str(attr_value)
    return attributes


def get_function_parameters(obj: Any) -> List[Dict[str, Any]]:
    """
    Get the parameters of a function object.

    Args:
        obj (Any): The function object.

    Returns:
        List[Dict[str, Any]]: A list of dictionaries representing the function parameters.
    """
    parameters = []
    try:
        sig = inspect.signature(obj)
        for param_name, param in sig.parameters.items():
            param_info = {
                'name': param_name,
                'type': str(param.annotation) if param.annotation != inspect.Parameter.empty else None,
                'default': str(param.default) if param.default != inspect.Parameter.empty else None
            }
            parameters.append(param_info)
    except (ValueError, TypeError):
        pass
    return parameters


def get_function_return_type(obj: Any) -> Optional[str]:
    """
    Get the return type of a function object.

    Args:
        obj (Any): The function object.

    Returns:
        Optional[str]: The string representation of the return type, or None if not available.
    """
    try:
        sig = inspect.signature(obj)
        return_type = sig.return_annotation
        return str(return_type) if return_type != inspect.Signature.empty else None
    except (ValueError, TypeError):
        return None


def get_object_dependencies(obj: Any, source_code: str) -> Dict[str, List[str]]:
    try:
        tree = ast.parse(source_code)
        local_dependencies = set()
        imported_dependencies = set()
        stdlib_dependencies = set()

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name in sys.stdlib_module_names:
                        stdlib_dependencies.add(alias.name)
                    else:
                        imported_dependencies.add(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module in sys.stdlib_module_names:
                    stdlib_dependencies.add(node.module)
                else:
                    imported_dependencies.add(node.module)
            elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
                if hasattr(obj, '__module__'):
                    module = sys.modules.get(obj.__module__)
                    if module and hasattr(module, node.id):
                        attr = getattr(module, node.id)
                        if inspect.ismodule(attr):
                            if attr.__name__ in sys.stdlib_module_names:
                                stdlib_dependencies.add(attr.__name__)
                            else:
                                imported_dependencies.add(attr.__name__)
                        elif (inspect.isfunction(attr) or inspect.isclass(attr)) and hasattr(attr, '__module__') and attr.__module__ == module.__name__:
                            local_dependencies.add(node.id)
                elif hasattr(obj, node.id):
                    attr = getattr(obj, node.id)
                    if hasattr(attr, '__module__') and attr.__module__ == 'builtins':
                        stdlib_dependencies.add(node.id)

        return {
            'local': list(local_dependencies),
            'imported': list(imported_dependencies),
            'stdlib': list(stdlib_dependencies)
        }
    except (SyntaxError, TypeError, AttributeError) as e:
        print(f"Error occurred while parsing dependencies for object {obj}: {str(e)}")
        return None