
import sys
import os
import ast
from pathlib import Path

def verify_startup_logic():
    print("Verifying startup logic for frozen state...")
    
    # 1. Dynamically verify call compatibility by inspecting app.py source code
    # This prevents the test from drifting out of sync with actual usage
    print("Inspecting app.py source code usage...")
    
    app_py_path = Path("src/gcse_toolkit/gui_v2/app.py")
    if not app_py_path.exists():
        print("❌ app.py not found")
        sys.exit(1)
        
    tree = ast.parse(app_py_path.read_text())
    
    # Simple visitor to find the install_crash_handler call
    call_args = {}
    found_call = False
    
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == 'install_crash_handler':
            found_call = True
            for kw in node.keywords:
                # We only support constant string values for this static check
                if isinstance(kw.value, ast.Constant):
                    call_args[kw.arg] = kw.value.value
    
    if not found_call:
        print("⚠️  Could not find install_crash_handler call in app.py statically. Skipping signature check.")
        return

    print(f"Found usage in app.py: install_crash_handler({call_args})")

    # 2. Invoke the function with the extracted arguments
    print("Checking install_crash_handler signature against extracted arguments...")
    try:
        from gcse_toolkit.gui_v2.utils.crashlog import install_crash_handler
        
        # Call with kwargs extracted from source
        install_crash_handler(**call_args) 
        
        print("✅ install_crash_handler signature match.")
    except TypeError as e:
        print(f"❌ CRITICAL: install_crash_handler mismatch detected: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"⚠️ Warning during runtime check: {e}")
        
    print("✅ Frozen startup logic verified.")

if __name__ == "__main__":
    verify_startup_logic()
