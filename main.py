from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
import os
import pandas as pd

app = FastAPI()

def load_menu() -> pd.DataFrame:
    if not os.path.exists("menu.csv"):
        return pd.DataFrame(columns=["id", "name", "price", "availability"])
    return pd.read_csv("menu.csv")

def save_menu(df: pd.DataFrame):
    df.to_csv("menu.csv", index=False)

def load_logs() -> pd.DataFrame:
    if not os.path.exists("log.csv"):
        return pd.DataFrame(columns=["order_id", "timestamp", "items", "subtotal", "discount", "tax", "total"])
    return pd.read_csv("log.csv")

def save_logs(df: pd.DataFrame):
    df.to_csv("log.csv", index=False)

class FoodItem(BaseModel):
    name: str
    price: float
    availability: bool

class OrderItem(BaseModel):
    item_id: int
    quantity: int

class OrderRequest(BaseModel):
    items: List[OrderItem]
    discount_code: Optional[str] = None

@app.get("/menu")
def get_menu():
    menus = load_menu()
    return menus.to_dict(orient="records")

@app.post("/admin/add")
def add_items(item_details: FoodItem):
    df = load_menu()
    
    if df.empty or "id" not in df.columns:
        new_id = 1
    else:
        new_id = int(df["id"].max() + 1)
        
    new_item = {
        "id": new_id,
        "name": item_details.name,
        "price": item_details.price,
        "availability": item_details.availability
    }
    
    df = pd.concat([df, pd.DataFrame([new_item])], ignore_index=True)
    save_menu(df)

    return {"message": "food item inserted successfully..", "id": new_id}

@app.post("/order")
def place_order(order: OrderRequest):
    menu_df = load_menu()
    if menu_df.empty:
        raise HTTPException(status_code=400, detail="Menu is empty")

    subtotal = 0.0
    ordered_items_summary = []

    for ordered_item in order.items:
        match = menu_df[menu_df["id"] == ordered_item.item_id]
        if match.empty:
            raise HTTPException(status_code=404, detail=f"Item ID {ordered_item.item_id} not found")
        
        row = match.iloc[0]
        if not row["availability"]:
            raise HTTPException(status_code=400, detail=f"Item '{row['name']}' is currently unavailable")
        
        item_total = float(row["price"]) * ordered_item.quantity
        subtotal += item_total
        ordered_items_summary.append(f"{row['name']} x{ordered_item.quantity}")

    discount = 0.0
    if order.discount_code:
        if order.discount_code.upper() == "SAVE10":
            discount = subtotal * 0.10
        elif order.discount_code.upper() == "FLAT50":
            discount = 50.0 if subtotal >= 50.0 else subtotal

    taxable_amount = subtotal - discount
    tax = taxable_amount * 0.05
    total = taxable_amount + tax

    logs_df = load_logs()
    new_order_id = int(logs_df["order_id"].max() + 1) if not logs_df.empty and "order_id" in logs_df.columns else 1
    
    log_record = {
        "order_id": new_order_id,
        "timestamp": datetime.now().isoformat(),
        "items": ", ".join(ordered_items_summary),
        "subtotal": round(subtotal, 2),
        "discount": round(discount, 2),
        "tax": round(tax, 2),
        "total": round(total, 2)
    }

    logs_df = pd.concat([logs_df, pd.DataFrame([log_record])], ignore_index=True)
    save_logs(logs_df)

    return {
        "message": "Order placed successfully",
        "bill": {
            "order_id": new_order_id,
            "items": ordered_items_summary,
            "subtotal": round(subtotal, 2),
            "discount": round(discount, 2),
            "tax": round(tax, 2),
            "total": round(total, 2)
        }
    }

@app.get("/orders/history")
def get_order_history():
    logs_df = load_logs()
    if logs_df.empty:
        return []
    return logs_df.to_dict(orient="records")

@app.get("/sales/today")
def get_todays_sales_summary():
    logs_df = load_logs()
    if logs_df.empty or "timestamp" not in logs_df.columns:
        return {
            "date": datetime.now().strftime("%Y-%m-%d"),
            "total_orders": 0,
            "total_revenue": 0.0,
            "total_discounts_given": 0.0,
            "total_tax_collected": 0.0
        }


    logs_df["date"] = pd.to_datetime(logs_df["timestamp"]).dt.strftime("%Y-%m-%d")
    today_str = datetime.now().strftime("%Y-%m-%d")
    
    today_df = logs_df[logs_df["date"] == today_str]

    if today_df.empty:
        return {
            "date": today_str,
            "total_orders": 0,
            "total_revenue": 0.0,
            "total_discounts_given": 0.0,
            "total_tax_collected": 0.0
        }

    return {
        "date": today_str,
        "total_orders": int(len(today_df)),
        "total_revenue": round(float(today_df["total"].sum()), 2),
        "total_discounts_given": round(float(today_df["discount"].sum()), 2),
        "total_tax_collected": round(float(today_df["tax"].sum()), 2)
    }