import pandas as pd

df = pd.read_csv("monsters.csv/Dd5e_monsters.csv")
print("Rows and columns:", df.shape)
print()
print("Column names:")
print(list(df.columns))
print()
print(df.head(5).to_string())
print()
print(df.dtypes)