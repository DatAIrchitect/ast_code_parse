import anthropic
import ast
from typing import Dict, List, Union
from pydantic import BaseModel


client = anthropic.Anthropic(api_key="CLAUDE_API_KEY")

class ContentBlock(BaseModel):
    text: str

def extract_code_and_imports(content_block: ContentBlock) -> Dict[str, Union[str, List[str]]]:
    """
    Extract Python code and import statements from a ContentBlock object which is returned from calling the Claude API using function ask_claude_code.

    Args:
        content_block (ContentBlock): The ContentBlock object containing the code.

    Returns:
        dict: A dictionary with keys 'code' and 'imports', where 'code' contains the extracted Python code as a string,
              and 'imports' contains a list of import statements.

    Raises:
        ValueError: If the content block does not contain a valid Python code block.
    """
    code_text = content_block[0].text.strip()

    # Find the start and end indices of the Python code block
    start_index = code_text.find("```python")
    end_index = code_text.find("```", start_index + len("```python"))

    if start_index == -1 or end_index == -1:
        raise ValueError("Invalid Python code block in the content.")

    # Extract the Python code block
    code_text = code_text[start_index + len("```python"):end_index].strip()

    try:
        tree = ast.parse(code_text)
    except SyntaxError as e:
        raise ValueError(f"Invalid Python syntax in the code block: {str(e)}")

    imports = []
    code_lines = []

    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            import_text = ast.unparse(node)
            imports.append(import_text)
        else:
            code_lines.append(ast.unparse(node))

    code = "\n".join(code_lines)
    result = {"code": code, "imports": imports}

    return result

def ask_claude_code(user_query: str):
    # TODO Handle situation where multiple objects are returned into a list.
    # TODO Handle situation where the code is not returned in the expected format
    # TODO Handle situation where the code is not returned at all
    # TODO Add feature that allows claude to return a list of tasks, attached to func names

    message = client.messages.create(
        model="claude-3-opus-20240229",
        max_tokens=3900,
        temperature=0.5,
        system="""I will refer to you as //Ψ𝚯Ξ⊱ℂ𝕃𝔸𝖀𝕯𝕰⊰Ξ𝚯Ψ//\n\n
        I will ask python based questions, and you return high quality, and pythonic code as a response.\n\n
        You do not include any explanations, or additional context, only the code.\n\n
        If you need to include comments, then do so within the docstring, or # , and do not return any text that cannot be compiled.

        You should always annotate your code, and include type hints where possible.\n\n
        You should always include the necessary imports, and ensure that the code is complete, and can be run without any additional code.\n\n
        Write clean, and concise code, and ensure that the code is well formatted.\n\n""",

        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": user_query
                    }
                ]
            }
        ]
    )
    # print(f"Code Returned from Claude : {message.content}")
    try:
        return extract_code_and_imports(message.content)
    except Exception as e:
        print(f"Failed to parse the python code with exception : {e}")
        return message.content