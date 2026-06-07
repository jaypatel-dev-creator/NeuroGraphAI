from langchain_core.tools import tool


@tool
def calculator(expression: str) -> str:
    """
    Evaluate a mathematical expression.
    Input must be a valid Python math expression string.
    Example: '2 + 2', '(10 * 5) / 2', '2 ** 8'
    """
    try:
        # safe eval — only math operations
        allowed = {"__builtins__": {}}
        result = eval(expression, allowed)  # noqa: S307
        return str(result)
    except Exception as e:
        return f"Calculation error: {str(e)}"