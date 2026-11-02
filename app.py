import streamlit as st
import pandas as pd
import numpy as np
import re
import io
import unicodedata

st.set_page_config(page_title="Household Water Usage Analysis", layout="wide")

st.markdown("""
<style>
.stTabs [data-baseweb="tab-list"] { gap: 8px; }
.stTabs [data-baseweb="tab"] {
    height: 46px; background-color: #f0f4f8; border: 1px solid #cdd7e2;
    border-radius: 6px; padding: 0 18px; color: #24435f; font-weight: 600;
}
.stTabs [aria-selected="true"] {
    background-color: #1f4e79 !important; color: #ffffff !important; border-color: #1f4e79 !important;
}
.stTabs [data-baseweb="tab-highlight"], .stTabs [data-baseweb="tab-border"] { display: none; }
div[data-testid="stMetric"] {
    background-color: #f7fafc; border: 1px solid #dbe4ed; border-radius: 8px; padding: 12px;
}
</style>
""", unsafe_allow_html=True)

EXAMPLE_PATH = "FINAL DATA SET 3.xlsx"

def clean_text(val):
    if pd.isna(val):
        return ""
    s = str(val)
    s = unicodedata.normalize("NFKD", s)
    s = re.sub(r"[\U0001F000-\U0001FAFF\u2600-\u27BF]", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s

def load_example():
    try:
        return pd.read_excel(EXAMPLE_PATH)
    except Exception:
        return None

def normalize_columns(df):
    df = df.copy()
    df.columns = [clean_text(c) for c in df.columns]
    return df

def find_col(df, keywords, fallback=None):
    for c in df.columns:
        cu = c.upper()
        if all(k.upper() in cu for k in keywords):
            return c
    return fallback

def parse_daily_liters(val):
    s = clean_text(val).upper()
    if s == "":
        return np.nan
    nums = re.findall(r"\d+", s.replace(",", ""))
    if not nums:
        return np.nan
    if "MORE THAN 300" in s or "MORE THAN300" in s:
        return 350.0
    if "LESS THAN 50" in s:
        return 25.0
    if len(nums) >= 2:
        lo, hi = float(nums[0]), float(nums[1])
        return (lo + hi) / 2.0
    return float(nums[0])

def parse_bill(val):
    s = clean_text(val).upper()
    if s == "" or "NO WATER BILL" in s:
        return np.nan
    if "ABOVE 1,000" in s or "ABOVE 1000" in s:
        return 1200.0
    nums = re.findall(r"\d[\d,]*", s)
    nums = [float(n.replace(",", "")) for n in nums]
    if not nums:
        return np.nan
    if len(nums) >= 2:
        return (nums[0] + nums[1]) / 2.0
    return nums[0]

def clean_dataset(df):
    df = normalize_columns(df)
    df = df.dropna(how="all")
    df = df.drop_duplicates()
    for c in df.columns:
        if df[c].dtype == object:
            df[c] = df[c].apply(clean_text)
    return df.reset_index(drop=True)

activity_cols = [
    "DRINGKING & COOKING", "BATHING", "LAUNDRY", "TOILET FLUSHING",
    "DISHWASHING", "CLEANING /MOPPING", "WATERING PLANTS",
    "CAR /VIHICLE WASHING", "ANIMAL CARE"
]

activity_labels = {
    "DRINGKING & COOKING": "Drinking & Cooking",
    "BATHING": "Bathing",
    "LAUNDRY": "Laundry",
    "TOILET FLUSHING": "Toilet Flushing",
    "DISHWASHING": "Dishwashing",
    "CLEANING /MOPPING": "Cleaning / Mopping",
    "WATERING PLANTS": "Watering Plants",
    "CAR /VIHICLE WASHING": "Car / Vehicle Washing",
    "ANIMAL CARE": "Animal Care"
}

freq_map = {"NEVER": 0, "RARELY": 1, "MONTHLY": 2, "WEEKLY": 3, "DAILY": 4}

st.sidebar.header("Data Source")
uploaded = st.sidebar.file_uploader("Upload CSV or Excel", type=["csv", "xlsx", "xls"])
use_example = st.sidebar.checkbox("Use example dataset (if no upload)", value=True)

df_raw = None
if uploaded is not None:
    try:
        if uploaded.name.lower().endswith(".csv"):
            df_raw = pd.read_csv(uploaded)
        else:
            df_raw = pd.read_excel(uploaded)
    except Exception as e:
        st.sidebar.error(f"Could not read file: {e}")
elif use_example:
    df_raw = load_example()

if df_raw is None:
    st.info("No dataset loaded. Upload a CSV or Excel file, or enable the example dataset in the sidebar.")
    st.stop()

df = clean_dataset(df_raw)

col_family = find_col(df, ["NUMBER OF LIVING"])
col_income = find_col(df, ["MONTHLY", "INCOME"])
col_source = find_col(df, ["PRIMARY SOURCE", "WATER"])
col_daily = find_col(df, ["AVERAGE DAILY HOUSEHOLD WATER"])
col_bill = find_col(df, ["AVERAGE MONTHLY WATER BILL"])
col_conserve = find_col(df, ["PRACTICE WATER CONSERVATION"])
col_practice = find_col(df, ["WHICH OF THE FOLLOWING WATER CONSERVATION"])
col_most = find_col(df, ["WHICH HUSEHOLD ACTIVITY CONSUMES"])
col_quality = find_col(df, ["RATE THE QUALITY OF WATER"])
col_shortage = find_col(df, ["EXPERIENCE WATER SHORTAGE"])
col_availability = find_col(df, ["WATER SUPPLY AVAILABLE"])

if col_daily:
    df["DailyLiters"] = df[col_daily].apply(parse_daily_liters)
if col_bill:
    df["MonthlyBill"] = df[col_bill].apply(parse_bill)

if col_daily:
    valid = df["DailyLiters"].dropna()
    if len(valid) >= 6:
        q1, q2 = valid.quantile(0.33), valid.quantile(0.66)
        def bin_level(x):
            if pd.isna(x):
                return np.nan
            if x <= q1:
                return "Low"
            if x <= q2:
                return "Medium"
            return "High"
        df["ConsumptionLevel"] = df["DailyLiters"].apply(bin_level)
    else:
        df["ConsumptionLevel"] = np.nan

family_map = {
    "1-2 PERSON": 1.5, "3-4 PERSON": 3.5, "5-6 PERSON": 5.5,
    "7-8 PERSON": 7.5, "9 OR MORE": 9.5
}
if col_family:
    df["FamilySizeNum"] = df[col_family].str.upper().map(family_map)

income_map = {
    "5000": 5000, "5,000": 5000, "5,000-10,000": 7500, "10,000-15,000": 12500,
    "15,000,20,000": 17500, "15,000-20,000": 17500, "20,000-30,000": 25000,
    "ABOVE 30,000": 35000
}
if col_income:
    df["IncomeNum"] = df[col_income].str.upper().map(income_map)

tabs = st.tabs([
    "Consumption Profile",
    "Clustering (K-Means)",
    "Classification (Decision Tree)",
    "Association Rules (Apriori)",
    "Conservation & Usage Patterns"
])

with tabs[0]:
    st.subheader("Household Consumption Profile")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Households", len(df))
    if "DailyLiters" in df:
        c2.metric("Mean Daily Use (L)", f"{df['DailyLiters'].mean():.1f}")
        c3.metric("Median Daily Use (L)", f"{df['DailyLiters'].median():.1f}")
    if "MonthlyBill" in df:
        c4.metric("Mean Monthly Bill", f"{df['MonthlyBill'].mean():.0f}")

    st.markdown("**Consumption Level Distribution**")
    if "ConsumptionLevel" in df and df["ConsumptionLevel"].notna().any():
        lvl = df["ConsumptionLevel"].value_counts().reindex(["Low", "Medium", "High"]).fillna(0)
        lvl_df = pd.DataFrame({"Level": lvl.index, "Households": lvl.values})
        st.bar_chart(lvl_df.set_index("Level"))
        st.write(lvl_df)
        st.write("Households are split into tertiles of reported daily use, giving equal-size low, medium, and high groups.")
    else:
        st.write("Insufficient daily consumption data to derive levels.")

    st.markdown("**Daily Use by Family Size**")
    if "FamilySizeNum" in df and df["FamilySizeNum"].notna().any():
        grp = df.dropna(subset=["FamilySizeNum", "DailyLiters"]).groupby("FamilySizeNum")["DailyLiters"].mean().reset_index()
        grp["FamilySizeNum"] = grp["FamilySizeNum"].astype(str)
        st.bar_chart(grp.set_index("FamilySizeNum"))
        st.write(grp)

    st.markdown("**Daily Use by Income Band**")
    if "IncomeNum" in df and df["IncomeNum"].notna().any():
        gi = df.dropna(subset=["IncomeNum", "DailyLiters"]).groupby("IncomeNum")["DailyLiters"].mean().reset_index()
        gi["IncomeNum"] = gi["IncomeNum"].astype(int).astype(str)
        st.bar_chart(gi.set_index("IncomeNum"))
        st.write(gi)

    if col_source:
        st.markdown("**Households by Water Source**")
        src = df[col_source].value_counts().reset_index()
        src.columns = ["Source", "Households"]
        st.bar_chart(src.set_index("Source"))
        st.write(src)

with tabs[1]:
    st.subheader("K-Means Clustering")
    feature_cols = [c for c in ["FamilySizeNum", "IncomeNum", "DailyLiters", "MonthlyBill"] if c in df and df[c].notna().any()]
    cluster_ready = df.dropna(subset=feature_cols) if feature_cols else pd.DataFrame()

    if len(cluster_ready) >= 8 and len(feature_cols) >= 2:
        from sklearn.preprocessing import StandardScaler
        from sklearn.cluster import KMeans
        from sklearn.metrics import silhouette_score, davies_bouldin_score

        X = cluster_ready[feature_cols].values
        Xs = StandardScaler().fit_transform(X)
        max_k = min(6, len(cluster_ready) - 1)
        ks = list(range(2, max_k + 1))
        wcss, sil, dbi = [], [], []
        for k in ks:
            km = KMeans(n_clusters=k, n_init=10, random_state=42).fit(Xs)
            wcss.append(km.inertia_)
            sil.append(silhouette_score(Xs, km.labels_))
            dbi.append(davies_bouldin_score(Xs, km.labels_))
        metrics_df = pd.DataFrame({"k": ks, "WCSS": wcss, "Silhouette": sil, "DaviesBouldin": dbi})
        st.write("**Elbow (WCSS) by k**")
        st.line_chart(metrics_df.set_index("k")["WCSS"])
        st.write(metrics_df)
        best_k = ks[int(np.argmax(sil))]
        st.metric("Selected k (max silhouette)", best_k)
        km = KMeans(n_clusters=best_k, n_init=10, random_state=42).fit(Xs)
        cluster_ready = cluster_ready.copy()
        cluster_ready["Cluster"] = km.labels_
        prof = cluster_ready.groupby("Cluster")[feature_cols].mean().round(2)
        prof["Households"] = cluster_ready.groupby("Cluster").size()
        st.write("**Cluster Profiles (means)**")
        st.dataframe(prof)
        st.write(f"The silhouette-optimal solution uses {best_k} clusters; Davies-Bouldin of {dbi[ks.index(best_k)]:.3f} indicates cluster separation quality.")
    else:
        st.write("Not enough complete records for clustering.")

with tabs[2]:
    st.subheader("Decision Tree Classification")
    if "ConsumptionLevel" in df and df["ConsumptionLevel"].notna().sum() >= 12:
        from sklearn.tree import DecisionTreeClassifier, export_text
        from sklearn.model_selection import train_test_split
        from sklearn.metrics import accuracy_score, precision_recall_fscore_support, confusion_matrix
        from sklearn.preprocessing import LabelEncoder

        feat = [c for c in ["FamilySizeNum", "IncomeNum", "MonthlyBill"] if c in df and df[c].notna().any()]
        tree_df = df.dropna(subset=feat + ["ConsumptionLevel"])
        if len(tree_df) >= 12 and feat:
            X = tree_df[feat].values
            y = tree_df["ConsumptionLevel"].values
            Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)
            clf = DecisionTreeClassifier(max_depth=4, random_state=42).fit(Xtr, ytr)
            pred = clf.predict(Xte)
            acc = accuracy_score(yte, pred)
            p, r, f1, _ = precision_recall_fscore_support(yte, pred, average="macro", zero_division=0)
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Accuracy", f"{acc:.3f}")
            c2.metric("Precision (macro)", f"{p:.3f}")
            c3.metric("Recall (macro)", f"{r:.3f}")
            c4.metric("F1 (macro)", f"{f1:.3f}")
            labels = sorted(set(yte) | set(pred))
            cm = confusion_matrix(yte, pred, labels=labels)
            cm_df = pd.DataFrame(cm, index=[f"Actual {l}" for l in labels], columns=[f"Pred {l}" for l in labels])
            st.write("**Confusion Matrix**")
            st.dataframe(cm_df)
            st.write("**Decision Rules**")
            st.text(export_text(clf, feature_names=feat))
            st.write("Accuracy above the 0.70 threshold indicates the model separates low, medium, and high consumers from household attributes reliably.")
        else:
            st.write("Insufficient features for classification.")
    else:
        st.write("Insufficient labeled records for classification.")

with tabs[3]:
    st.subheader("Apriori Association Rules")
    try:
        from mlxtend.frequent_patterns import apriori, association_rules
        arm_cols = []
        if col_family: arm_cols.append(col_family)
        if col_income: arm_cols.append(col_income)
        if col_source: arm_cols.append(col_source)
        if "ConsumptionLevel" in df and df["ConsumptionLevel"].notna().any():
            arm_cols.append("ConsumptionLevel")
        arm_df = df[arm_cols].dropna()
        if len(arm_df) >= 10 and len(arm_cols) >= 2:
            trans = pd.get_dummies(arm_df.astype(str))
            trans = trans.loc[:, trans.sum() / len(trans) >= 0.10]
            if trans.shape[1] >= 3:
                freq = apriori(trans, min_support=0.10, use_colnames=True)
                if len(freq) > 0:
                    rules = association_rules(freq, metric="confidence", min_threshold=0.60)
                    rules = rules[rules["lift"] > 1.0].sort_values("lift", ascending=False)
                    if len(rules) > 0:
                        show = rules[["antecedents", "consequents", "support", "confidence", "lift"]].copy()
                        show["antecedents"] = show["antecedents"].apply(lambda s: ", ".join(sorted(s)))
                        show["consequents"] = show["consequents"].apply(lambda s: ", ".join(sorted(s)))
                        st.dataframe(show.reset_index(drop=True))
                        st.write(f"{len(show)} rules meet support >= 0.10, confidence >= 0.60, and lift > 1.0.")
                        top = show.head(10).copy()
                        top["rule"] = top["antecedents"] + " -> " + top["consequents"]
                        st.bar_chart(top.set_index("rule")["lift"])
                    else:
                        st.write("No rules met the confidence and lift thresholds.")
                else:
                    st.write("No frequent itemsets at the support threshold.")
            else:
                st.write("Too few qualifying items for rule mining.")
        else:
            st.write("Insufficient records for association rule mining.")
    except ImportError:
        st.write("Association rule library is unavailable in this environment.")

with tabs[4]:
    st.subheader("Conservation & Usage Patterns")
    act_present = [c for c in activity_cols if c in df.columns]
    if act_present:
        st.markdown("**Activity Frequency Profile**")
        rows = []
        for c in act_present:
            counts = df[c].str.upper().value_counts()
            for k, v in counts.items():
                rows.append({"Activity": activity_labels.get(c, c), "Frequency": k, "Households": v})
        af = pd.DataFrame(rows)
        pivot = af.pivot_table(index="Activity", columns="Frequency", values="Households", aggfunc="sum").fillna(0)
        order = [x for x in ["DAILY", "WEEKLY", "MONTHLY", "RARELY", "NEVER"] if x in pivot.columns]
        pivot = pivot[order]
        st.bar_chart(pivot)
        st.write(pivot)

    if col_most:
        st.markdown("**Activity Consuming Most Water**")
        mw = df[col_most].value_counts().reset_index()
        mw.columns = ["Activity", "Households"]
        st.bar_chart(mw.set_index("Activity"))
        st.write(mw)

    if col_conserve:
        st.markdown("**Conservation Practice Adoption**")
        cp = df[col_conserve].value_counts().reset_index()
        cp.columns = ["Response", "Households"]
        st.bar_chart(cp.set_index("Response"))
        st.write(cp)

    if col_practice:
        st.markdown("**Top Conservation Methods Applied**")
        pm = df[col_practice].value_counts().head(10).reset_index()
        pm.columns = ["Method", "Households"]
        st.bar_chart(pm.set_index("Method"))
        st.write(pm)

    if col_shortage and col_source:
        st.markdown("**Water Shortage Experience by Source**")
        ct = pd.crosstab(df[col_source], df[col_shortage])
        st.write(ct)
        st.bar_chart(ct)
