# ml/config.py

# รายชื่อ Column ที่ใช้เป็น Input เข้า Model
# ต้องเรียงลำดับให้เหมือนกันเสมอทั้ง Train และ Predict
MODEL_FEATURES = [
    'Age', 
    'Height', 
    'BodyWeight', 
    'BMIValue', 
    'Start_Hour', 
    'Day_of_Week',
    'Doctor',           # Categorical
    'TreatmentCode',    # Categorical
    'Specialty',        # Categorical
    'Gender',           # Categorical
    'AnesthesiaType',   # Categorical
    'ORCaseType',       # Categorical
    'ORClassifiedType', # Categorical
    'FacilityRmsNo'     # Categorical
]

# รายชื่อ Column ที่เป็นประเภทกลุ่ม (Category)
CAT_FEATURES = [
    'Doctor', 
    'TreatmentCode', 
    'Specialty', 
    'Gender', 
    'AnesthesiaType', 
    'ORCaseType', 
    'ORClassifiedType', 
    'FacilityRmsNo'
]