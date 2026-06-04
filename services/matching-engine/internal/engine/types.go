package engine

import "time"

type Side string

const (
	SideBuy  Side = "buy"
	SideSell Side = "sell"
)

type OrderType string

const (
	OrderTypeMarket OrderType = "market"
	OrderTypeLimit  OrderType = "limit"
)

type OrderStatus string

const (
	StatusNew       OrderStatus = "new"
	StatusPartial   OrderStatus = "partial_fill"
	StatusFilled    OrderStatus = "filled"
	StatusCancelled OrderStatus = "cancelled"
)

type Order struct {
	ID        string
	UserID    string
	Symbol    string
	Side      Side
	Type      OrderType
	Price     float64
	Quantity  int64
	Filled    int64
	Status    OrderStatus
	CreatedAt time.Time
}

func (o *Order) Remaining() int64 {
	return o.Quantity - o.Filled
}

func (o *Order) IsFilled() bool {
	return o.Filled >= o.Quantity
}

type Trade struct {
	ID          string
	Symbol      string
	BuyOrderID  string
	SellOrderID string
	BuyerID     string
	SellerID    string
	Price       float64
	Quantity    int64
	ExecutedAt  time.Time
}

type PriceLevel struct {
	Price  float64
	Orders []*Order
}

func (pl *PriceLevel) TotalQuantity() int64 {
	var total int64
	for _, o := range pl.Orders {
		total += o.Remaining()
	}
	return total
}