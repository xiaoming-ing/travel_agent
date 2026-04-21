/**
 * 前端类型定义，和 backend/app/schemas 完全对应。
 * 后端字段改了，这里也要跟着改 —— 两边保持同步。
 */

export interface TripRequest {
  destination: string
  start_date: string   // "YYYY-MM-DD"，<input type="date"> 的值就是这格式
  end_date: string
  transport: string
  accommodation: string
  preferences: string[]
  extra_requirements?: string | null
}

export interface Attraction {
  name: string
  address: string
  longitude: number
  latitude: number
  duration_minutes: number
  ticket_price: number
  description: string
  image_url: string | null
}

export interface Hotel {
  name: string
  address: string
  type: string
  price_range: string
  rating: number
  distance_note: string
  longitude: number
  latitude: number
}

export interface MealPlan {
  breakfast: string
  lunch: string
  dinner: string
}

export interface DailyPlan {
  day: number
  date: string
  description: string
  transport: string
  accommodation: string
  attraction_names: string[]
  meals: MealPlan
}

export interface BudgetBreakdown {
  attractions: number
  hotel: number
  meals: number
  transport: number
  total?: number   // 后端可能不返回，前端兜底计算
}

export interface TripPlan {
  destination: string
  start_date: string
  end_date: string
  trip_days: number
  suggestion: string
  budget: BudgetBreakdown
  attractions: Attraction[]
  daily_plans: DailyPlan[]
  hotels: Hotel[]           // 推荐住宿Top3，按交通方式+距离+评分综合排序
  weather_summary: string
}
