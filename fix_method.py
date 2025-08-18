#!/usr/bin/env python3

# Helper script to fix the get_creatives_report method
# We'll replace the entire method with our new implementation

import re

def fix_method():
    file_path = "/Users/evgenii/creative-keitaro-bot/src/integrations/keitaro/client.py"
    
    # Read the current file
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Find the start and end of the method
    start_pattern = r'async def get_creatives_report\('
    end_pattern = r'except Exception as e:\s+logger\.error\(f"Failed to get creatives report: {e}"\)\s+return \[\]'
    
    # Find start position
    start_match = re.search(start_pattern, content)
    if not start_match:
        print("Could not find method start")
        return
    
    start_pos = start_match.start()
    
    # Find end position (looking for the exception handler)
    end_match = re.search(end_pattern, content[start_pos:])
    if not end_match:
        print("Could not find method end")
        return
    
    end_pos = start_pos + end_match.end()
    
    # Extract the method signature and create the new method
    method_signature = content[start_pos:content.find(':', start_pos) + 1]
    method_docstring = '''
        """Get detailed creatives statistics using raw conversions data
        
        FIXED: Now uses sub_id_2 (actual creative ID) instead of sub_id_4
        
        Returns list of creative stats including:
        - creative_id (from sub_id_2 - actual creative ID field)
        - buyer_id (from sub_id_1)
        - geo/country
        - clicks, unique_clicks, conversions, deposits, revenue
        - uEPC (revenue per unique click)
        - active_days (days with 10+ clicks)
        """'''
    
    new_method = f'''    {method_signature[4:]}  # Remove leading spaces
        period: ReportPeriod = ReportPeriod.YESTERDAY,
        buyer_id: Optional[str] = None,
        geo: Optional[str] = None,
        traffic_source_ids: Optional[List[str]] = None,
        custom_start: Optional[str] = None,
        custom_end: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        {method_docstring}
        
        # Method implementation will be added here
        pass'''
    
    print(f"Method found from position {start_pos} to {end_pos}")
    print(f"Length: {end_pos - start_pos} characters")
    
    # For now, just print what we found
    print("\nMethod signature:")
    print(method_signature)

if __name__ == "__main__":
    fix_method()