import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

df = pd.read_csv("../data/processed/clean_dataset.csv")

plt.figure(figsize=(12,8))
sns.heatmap(df.corr(numeric_only=True),annot=True,cmap="viridis")
plt.savefig("../plots/correlation_heatmap.png")
plt.show()

plt.figure(figsize=(8,5))
sns.histplot(df["Temperature"],bins=30)
plt.savefig("../plots/temp_distribution.png")
plt.show()

plt.figure(figsize=(8,5))
sns.boxplot(y=df["GHI"])
plt.savefig("../plots/ghi_boxplot.png")
plt.show()

plt.figure(figsize=(8,5))
sns.scatterplot(x=df["Temperature"],y=df["GHI"])
plt.savefig("../plots/temp_vs_ghi.png")
plt.show()