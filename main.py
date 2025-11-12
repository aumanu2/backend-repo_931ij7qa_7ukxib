import os
from typing import List, Any, Dict
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from bson import ObjectId

from database import db, create_document, get_documents
from schemas import Product as ProductSchema, Order as OrderSchema, OrderItem as OrderItemSchema

app = FastAPI(title="Ecommerce API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def serialize_doc(doc: Dict[str, Any]):
    if not doc:
        return doc
    out = {}
    for k, v in doc.items():
        if k == "_id":
            out["id"] = str(v)
        elif hasattr(v, "isoformat"):
            out[k] = v.isoformat()
        else:
            out[k] = v
    return out


@app.get("/")
def read_root():
    return {"message": "Ecommerce backend is running"}


@app.get("/test")
def test_database():
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }
    try:
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
            response["database_name"] = db.name
            response["connection_status"] = "Connected"
            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️  Connected but Error: {str(e)[:50]}"
        else:
            response["database"] = "⚠️  Available but not initialized"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:50]}"
    return response


# Products
@app.get("/api/products")
def list_products(limit: int = 100):
    docs = get_documents("product", {}, limit)
    return [serialize_doc(d) for d in docs]


@app.get("/api/products/seed")
def seed_products():
    existing = db["product"].count_documents({}) if db else 0
    if existing > 0:
        return {"message": "Products already exist", "count": existing}
    samples = [
        ProductSchema(title="Classic Tee", description="Soft cotton t-shirt", price=19.99, category="Apparel", image="https://images.unsplash.com/photo-1520975916090-3105956dac38?q=80&w=1200&auto=format&fit=crop", in_stock=True, stock_qty=100),
        ProductSchema(title="Denim Jacket", description="All-season denim jacket", price=59.0, category="Apparel", image="https://images.unsplash.com/photo-1548883354-7622d03aca27?q=80&w=1200&auto=format&fit=crop", in_stock=True, stock_qty=40),
        ProductSchema(title="Sneakers", description="Comfortable everyday sneakers", price=79.5, category="Footwear", image="https://images.unsplash.com/photo-1525966222134-fcfa99b8ae77?q=80&w=1200&auto=format&fit=crop", in_stock=True, stock_qty=60),
        ProductSchema(title="Backpack", description="Durable travel backpack", price=45.0, category="Accessories", image="https://images.unsplash.com/photo-1504280390368-3971f6602f25?q=80&w=1200&auto=format&fit=crop", in_stock=True, stock_qty=80),
    ]
    ids = []
    for s in samples:
        ids.append(create_document("product", s))
    return {"message": "Seeded products", "ids": ids}


class CreateProductRequest(ProductSchema):
    pass


@app.post("/api/products")
def create_product(payload: CreateProductRequest):
    new_id = create_document("product", payload)
    doc = db["product"].find_one({"_id": ObjectId(new_id)})
    return serialize_doc(doc)


@app.get("/api/products/{product_id}")
def get_product(product_id: str):
    try:
        oid = ObjectId(product_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid product id")
    doc = db["product"].find_one({"_id": oid})
    if not doc:
        raise HTTPException(status_code=404, detail="Product not found")
    return serialize_doc(doc)


# Orders
class CreateOrderRequest(OrderSchema):
    pass


@app.post("/api/orders")
def create_order(order: CreateOrderRequest):
    # Validate items and compute totals server-side
    if not order.items or len(order.items) == 0:
        raise HTTPException(status_code=400, detail="No items in order")

    computed_subtotal = 0.0
    sanitized_items: List[OrderItemSchema] = []

    for item in order.items:
        try:
            oid = ObjectId(item.product_id)
        except Exception:
            raise HTTPException(status_code=400, detail=f"Invalid product id: {item.product_id}")
        prod = db["product"].find_one({"_id": oid})
        if not prod:
            raise HTTPException(status_code=404, detail=f"Product not found: {item.product_id}")
        if not prod.get("in_stock", True) or prod.get("stock_qty", 0) < item.quantity:
            raise HTTPException(status_code=400, detail=f"Insufficient stock for {prod.get('title', 'product')}")
        price = float(prod.get("price", 0))
        computed_subtotal += price * item.quantity
        sanitized_items.append(OrderItemSchema(
            product_id=str(prod["_id"]),
            title=prod.get("title", "Product"),
            price=price,
            quantity=item.quantity,
            image=prod.get("image")
        ))

    shipping = float(order.shipping or 0)
    total = round(computed_subtotal + shipping, 2)

    # Create order doc
    order_doc = OrderSchema(
        customer_name=order.customer_name,
        customer_email=order.customer_email,
        customer_address=order.customer_address,
        items=sanitized_items,
        subtotal=round(computed_subtotal, 2),
        shipping=round(shipping, 2),
        total=total,
        status="processing"
    )

    order_id = create_document("order", order_doc)

    # Decrement stock
    for it in sanitized_items:
        db["product"].update_one({"_id": ObjectId(it.product_id)}, {"$inc": {"stock_qty": -it.quantity}})

    created = db["order"].find_one({"_id": ObjectId(order_id)})
    return serialize_doc(created)


@app.get("/api/orders")
def list_orders(limit: int = 50):
    docs = get_documents("order", {}, limit)
    return [serialize_doc(d) for d in docs]


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
