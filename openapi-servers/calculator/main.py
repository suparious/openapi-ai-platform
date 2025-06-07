"""
Calculator OpenAPI Server
Provides mathematical calculation capabilities including basic arithmetic,
scientific functions, and symbolic mathematics
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List, Union
import math
import cmath
import numpy as np
import sympy as sp
from sympy.parsing.sympy_parser import parse_expr, standard_transformations, implicit_multiplication_application
import asyncio
import os
import logging
from decimal import Decimal, getcontext
import json

# Configure logging
logging.basicConfig(level=os.getenv('LOG_LEVEL', 'INFO'))
logger = logging.getLogger(__name__)

# Configuration
MAX_CALCULATION_TIME = int(os.getenv('MAX_CALCULATION_TIME', '30'))
ENABLE_SYMBOLIC = os.getenv('ENABLE_SYMBOLIC', 'true').lower() == 'true'
PRECISION = int(os.getenv('PRECISION', '50'))

# Set decimal precision
getcontext().prec = PRECISION

# Create FastAPI app
app = FastAPI(
    title="Calculator OpenAPI Server",
    description="Mathematical calculation service with support for arithmetic, scientific, and symbolic math",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv('CORS_ORIGINS', '*').split(','),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Models
class CalculationRequest(BaseModel):
    expression: str = Field(..., description="Mathematical expression to evaluate")
    variables: Optional[Dict[str, float]] = Field(None, description="Variables to substitute in the expression")
    mode: Optional[str] = Field("numeric", description="Calculation mode: numeric, symbolic, or auto")
    precision: Optional[int] = Field(None, description="Decimal precision for the result")
    output_format: Optional[str] = Field("default", description="Output format: default, latex, or json")

class CalculationResult(BaseModel):
    expression: str
    result: Union[float, str, Dict[str, Any]]
    mode: str
    steps: Optional[List[str]] = None
    latex: Optional[str] = None
    simplified: Optional[str] = None
    error: Optional[str] = None

class StatisticsRequest(BaseModel):
    data: List[float] = Field(..., description="List of numbers for statistical analysis")
    operations: Optional[List[str]] = Field(
        None, 
        description="Statistical operations to perform",
        example=["mean", "median", "std", "variance"]
    )

class MatrixRequest(BaseModel):
    operation: str = Field(..., description="Matrix operation: multiply, inverse, determinant, eigenvalues")
    matrix_a: List[List[float]] = Field(..., description="First matrix")
    matrix_b: Optional[List[List[float]]] = Field(None, description="Second matrix (for operations that need it)")

# Helper functions
def safe_eval(expression: str, variables: Optional[Dict[str, float]] = None) -> float:
    """Safely evaluate a mathematical expression"""
    # Define safe functions and constants
    safe_dict = {
        'abs': abs, 'round': round, 'min': min, 'max': max,
        'sum': sum, 'pow': pow, 'sqrt': math.sqrt,
        'sin': math.sin, 'cos': math.cos, 'tan': math.tan,
        'asin': math.asin, 'acos': math.acos, 'atan': math.atan,
        'sinh': math.sinh, 'cosh': math.cosh, 'tanh': math.tanh,
        'exp': math.exp, 'log': math.log, 'log10': math.log10,
        'ceil': math.ceil, 'floor': math.floor,
        'pi': math.pi, 'e': math.e,
        'factorial': math.factorial, 'gcd': math.gcd,
        'degrees': math.degrees, 'radians': math.radians,
    }
    
    # Add numpy functions
    safe_dict.update({
        'mean': np.mean, 'median': np.median, 'std': np.std,
        'var': np.var, 'dot': np.dot, 'cross': np.cross,
    })
    
    # Add variables if provided
    if variables:
        safe_dict.update(variables)
    
    # Remove dangerous characters
    if any(char in expression for char in ['__', 'import', 'exec', 'eval', 'open', 'file', 'input', 'raw_input']):
        raise ValueError("Unsafe expression detected")
    
    try:
        # Use compile to check syntax
        compiled = compile(expression, '<string>', 'eval')
        # Evaluate with restricted namespace
        result = eval(compiled, {"__builtins__": {}}, safe_dict)
        return float(result)
    except Exception as e:
        raise ValueError(f"Error evaluating expression: {str(e)}")

async def calculate_with_timeout(func, *args, **kwargs):
    """Execute a calculation with timeout"""
    try:
        return await asyncio.wait_for(
            asyncio.get_event_loop().run_in_executor(None, func, *args, **kwargs),
            timeout=MAX_CALCULATION_TIME
        )
    except asyncio.TimeoutError:
        raise HTTPException(status_code=408, detail="Calculation timeout")

# Routes
@app.get("/health")
async def health():
    """Health check endpoint"""
    return {"status": "healthy", "service": "calculator"}

@app.get("/openapi.json", include_in_schema=False)
async def get_openapi():
    """Get OpenAPI schema"""
    return app.openapi()

@app.post("/calculate", response_model=CalculationResult)
async def calculate(request: CalculationRequest) -> CalculationResult:
    """
    Perform mathematical calculations
    
    Supports:
    - Basic arithmetic: +, -, *, /, **, %
    - Scientific functions: sin, cos, tan, log, exp, sqrt, etc.
    - Constants: pi, e
    - Variables: Define variables in the 'variables' parameter
    - Symbolic math: Set mode='symbolic' for algebraic manipulation
    """
    try:
        result = CalculationResult(
            expression=request.expression,
            result=None,
            mode=request.mode
        )
        
        # Set precision if specified
        if request.precision:
            getcontext().prec = request.precision
        
        if request.mode == "symbolic" or (request.mode == "auto" and ENABLE_SYMBOLIC):
            # Symbolic calculation using SymPy
            try:
                # Parse expression with transformations
                transformations = standard_transformations + (implicit_multiplication_application,)
                expr = parse_expr(request.expression, transformations=transformations)
                
                # Substitute variables if provided
                if request.variables:
                    substitutions = [(sp.Symbol(var), val) for var, val in request.variables.items()]
                    expr = expr.subs(substitutions)
                
                # Simplify the expression
                simplified = sp.simplify(expr)
                
                # Try to evaluate numerically
                try:
                    numeric_result = float(simplified.evalf())
                    result.result = numeric_result
                except:
                    result.result = str(simplified)
                
                result.simplified = str(simplified)
                result.latex = sp.latex(simplified) if request.output_format == "latex" else None
                result.mode = "symbolic"
                
            except Exception as e:
                logger.error(f"Symbolic calculation failed: {e}")
                if request.mode == "symbolic":
                    raise
                # Fall back to numeric if in auto mode
                request.mode = "numeric"
        
        if request.mode == "numeric" or result.result is None:
            # Numeric calculation
            numeric_result = await calculate_with_timeout(
                safe_eval, 
                request.expression, 
                request.variables
            )
            
            # Handle precision
            if request.precision:
                result.result = float(Decimal(str(numeric_result)))
            else:
                result.result = numeric_result
            
            result.mode = "numeric"
        
        # Format output
        if request.output_format == "json" and isinstance(result.result, (int, float)):
            result.result = {
                "value": result.result,
                "expression": request.expression,
                "variables": request.variables
            }
        
        return result
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Calculation error: {e}")
        raise HTTPException(status_code=500, detail=f"Calculation error: {str(e)}")

@app.post("/statistics")
async def statistics(request: StatisticsRequest) -> Dict[str, Any]:
    """
    Perform statistical calculations on a dataset
    
    Available operations:
    - mean: Average value
    - median: Middle value
    - mode: Most common value
    - std: Standard deviation
    - variance: Variance
    - min/max: Minimum and maximum values
    - sum: Sum of all values
    - count: Number of values
    - percentiles: 25th, 50th, 75th percentiles
    """
    if not request.data:
        raise HTTPException(status_code=400, detail="Data array cannot be empty")
    
    data = np.array(request.data)
    operations = request.operations or ["mean", "median", "std", "min", "max"]
    
    results = {}
    
    operation_map = {
        "mean": lambda d: float(np.mean(d)),
        "median": lambda d: float(np.median(d)),
        "std": lambda d: float(np.std(d)),
        "variance": lambda d: float(np.var(d)),
        "min": lambda d: float(np.min(d)),
        "max": lambda d: float(np.max(d)),
        "sum": lambda d: float(np.sum(d)),
        "count": lambda d: len(d),
        "percentiles": lambda d: {
            "25th": float(np.percentile(d, 25)),
            "50th": float(np.percentile(d, 50)),
            "75th": float(np.percentile(d, 75))
        }
    }
    
    for op in operations:
        if op in operation_map:
            try:
                results[op] = await calculate_with_timeout(operation_map[op], data)
            except Exception as e:
                results[op] = f"Error: {str(e)}"
        else:
            results[op] = "Unsupported operation"
    
    return {
        "data_points": len(request.data),
        "results": results
    }

@app.post("/matrix")
async def matrix_operations(request: MatrixRequest) -> Dict[str, Any]:
    """
    Perform matrix operations
    
    Supported operations:
    - multiply: Matrix multiplication
    - inverse: Matrix inverse
    - determinant: Matrix determinant
    - eigenvalues: Eigenvalues and eigenvectors
    - transpose: Matrix transpose
    - trace: Sum of diagonal elements
    """
    try:
        matrix_a = np.array(request.matrix_a)
        
        if request.operation == "multiply":
            if not request.matrix_b:
                raise HTTPException(status_code=400, detail="Second matrix required for multiplication")
            matrix_b = np.array(request.matrix_b)
            result = await calculate_with_timeout(np.matmul, matrix_a, matrix_b)
            return {"result": result.tolist()}
            
        elif request.operation == "inverse":
            result = await calculate_with_timeout(np.linalg.inv, matrix_a)
            return {"result": result.tolist()}
            
        elif request.operation == "determinant":
            result = await calculate_with_timeout(np.linalg.det, matrix_a)
            return {"result": float(result)}
            
        elif request.operation == "eigenvalues":
            eigenvalues, eigenvectors = await calculate_with_timeout(np.linalg.eig, matrix_a)
            return {
                "eigenvalues": eigenvalues.tolist(),
                "eigenvectors": eigenvectors.tolist()
            }
            
        elif request.operation == "transpose":
            result = matrix_a.T
            return {"result": result.tolist()}
            
        elif request.operation == "trace":
            result = np.trace(matrix_a)
            return {"result": float(result)}
            
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported operation: {request.operation}")
            
    except np.linalg.LinAlgError as e:
        raise HTTPException(status_code=400, detail=f"Linear algebra error: {str(e)}")
    except Exception as e:
        logger.error(f"Matrix operation error: {e}")
        raise HTTPException(status_code=500, detail=f"Matrix operation error: {str(e)}")

@app.get("/constants")
async def list_constants() -> Dict[str, float]:
    """List available mathematical constants"""
    return {
        "pi": math.pi,
        "e": math.e,
        "tau": math.tau,
        "inf": float('inf'),
        "nan": float('nan'),
        "golden_ratio": (1 + math.sqrt(5)) / 2,
        "euler_gamma": 0.5772156649015329,
        "sqrt2": math.sqrt(2),
        "sqrt3": math.sqrt(3),
        "sqrt5": math.sqrt(5)
    }

@app.get("/functions")
async def list_functions() -> Dict[str, List[str]]:
    """List available mathematical functions"""
    return {
        "basic": ["abs", "round", "min", "max", "sum", "pow"],
        "trigonometric": ["sin", "cos", "tan", "asin", "acos", "atan", "atan2"],
        "hyperbolic": ["sinh", "cosh", "tanh", "asinh", "acosh", "atanh"],
        "exponential": ["exp", "log", "log10", "log2", "sqrt"],
        "special": ["factorial", "gcd", "lcm", "ceil", "floor"],
        "conversion": ["degrees", "radians"],
        "complex": ["real", "imag", "abs", "phase"]
    }

@app.post("/solve")
async def solve_equation(equation: str, variable: str = "x") -> Dict[str, Any]:
    """
    Solve algebraic equations symbolically
    
    Examples:
    - Linear: "2*x + 5 = 15"
    - Quadratic: "x**2 - 5*x + 6 = 0"
    - System: Pass multiple equations
    """
    if not ENABLE_SYMBOLIC:
        raise HTTPException(status_code=501, detail="Symbolic math is disabled")
    
    try:
        # Parse the equation
        if "=" in equation:
            left, right = equation.split("=")
            expr = parse_expr(left) - parse_expr(right)
        else:
            expr = parse_expr(equation)
        
        # Solve for the variable
        var = sp.Symbol(variable)
        solutions = sp.solve(expr, var)
        
        # Convert solutions to JSON-serializable format
        solution_list = []
        for sol in solutions:
            try:
                # Try to convert to float
                numeric = float(sol.evalf())
                solution_list.append(numeric)
            except:
                # Keep as string if can't convert
                solution_list.append(str(sol))
        
        return {
            "equation": equation,
            "variable": variable,
            "solutions": solution_list,
            "solution_count": len(solution_list)
        }
        
    except Exception as e:
        logger.error(f"Equation solving error: {e}")
        raise HTTPException(status_code=400, detail=f"Error solving equation: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
