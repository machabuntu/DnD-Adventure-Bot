import json
from database import get_db

# Instantiate database manager
db = get_db()

# Connect to the database
if db.connect():
    try:
        # Retrieve the skills_available field for the Bard class
        query = "SELECT name, skills_available FROM classes WHERE name=%s"
        bard_name = ("Бард",)

        # Execute the query
        result = db.execute_query(query, bard_name)

        # Check and print the result
        if result:
            bard_class = result[0]
            class_name = bard_class['name']
            skills_available_raw = bard_class['skills_available']
            
            print(f'Class name: {class_name}')
            print(f'Skills available (raw): {skills_available_raw}')
            print(f'Type of skills_available: {type(skills_available_raw)}')
            
            # Try to parse as JSON
            try:
                skills_list = json.loads(skills_available_raw)
                print(f'Parsed skills list: {skills_list}')
                print(f'Number of skills: {len(skills_list)}')
                
                # Check if it contains "любые три"
                if "любые три" in skills_list:
                    print('Contains "любые три" - this is the issue!')
                else:
                    print('Does not contain "любые три"')
                    
            except json.JSONDecodeError as e:
                print(f'JSON parsing error: {e}')
                
        else:
            print('No Bard class found in the database.')
            
        # Also get all classes for comparison
        print('\n--- All classes ---')
        all_classes = db.execute_query("SELECT name, skills_available FROM classes")
        for cls in all_classes:
            print(f'{cls["name"]}: {cls["skills_available"][:50]}...')

    except Exception as error:
        print(f'Error occurred while fetching data: {error}')
    finally:
        # Disconnect from the database
        db.disconnect()
else:
    print("Failed to connect to the database.")
