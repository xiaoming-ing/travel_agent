

from langgraph.graph import StateGraph,START,END
from app.graph.state import TravelState
from app.agents.weather import weather_node
from app.agents.attraction import attraction_node
from app.agents.hotel import hotel_node
from app.agents.itinerary import itinerary_node

builder = StateGraph(TravelState)

builder.add_node("weather",weather_node)
builder.add_node("attraction",attraction_node)
builder.add_node("hotel",hotel_node)
builder.add_node("itinerary",itinerary_node)

# 扇出：weather 与 attraction 并行；hotel 依赖 attraction（要算景点重心）
builder.add_edge(START, "weather")
builder.add_edge(START, "attraction")
builder.add_edge("attraction", "hotel")

builder.add_edge("weather", "itinerary")
builder.add_edge("attraction", "itinerary")
builder.add_edge("hotel", "itinerary")

builder.add_edge("itinerary", END)

graph = builder.compile()