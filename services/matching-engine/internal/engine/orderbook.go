package engine

import (
	"fmt"
	"sort"
	"sync"
	"time"
)

type OrderBook struct {
	Symbol       string
	bids         []*PriceLevel
	asks         []*PriceLevel
	mu           sync.Mutex
	tradeCounter int64
}

func NewOrderBook(symbol string) *OrderBook {
	return &OrderBook{
		Symbol: symbol,
		bids:   make([]*PriceLevel, 0),
		asks:   make([]*PriceLevel, 0),
	}
}

func (ob *OrderBook) Submit(order *Order) ([]*Trade, *Order) {
	ob.mu.Lock()
	defer ob.mu.Unlock()

	order.CreatedAt = time.Now()
	order.Status = StatusNew

	var trades []*Trade

	if order.Side == SideBuy {
		trades = ob.matchBuy(order)
	} else {
		trades = ob.matchSell(order)
	}

	if !order.IsFilled() {
		if order.Type == OrderTypeMarket {
			order.Status = StatusCancelled
		} else {
			ob.addToBook(order)
		}
	}

	return trades, order
}

func (ob *OrderBook) matchBuy(order *Order) []*Trade {
	var trades []*Trade

	for len(ob.asks) > 0 && !order.IsFilled() {
		bestAsk := ob.asks[0]

		if order.Type == OrderTypeLimit && bestAsk.Price > order.Price {
			break
		}

		for len(bestAsk.Orders) > 0 && !order.IsFilled() {
			sellOrder := bestAsk.Orders[0]
			trade := ob.executeTrade(order, sellOrder, bestAsk.Price)
			trades = append(trades, trade)

			if sellOrder.IsFilled() {
				bestAsk.Orders = bestAsk.Orders[1:]
			}
		}

		if len(bestAsk.Orders) == 0 {
			ob.asks = ob.asks[1:]
		}
	}

	if len(trades) > 0 && !order.IsFilled() {
		order.Status = StatusPartial
	} else if order.IsFilled() {
		order.Status = StatusFilled
	}

	return trades
}

func (ob *OrderBook) matchSell(order *Order) []*Trade {
	var trades []*Trade

	for len(ob.bids) > 0 && !order.IsFilled() {
		bestBid := ob.bids[0]

		if order.Type == OrderTypeLimit && bestBid.Price < order.Price {
			break
		}

		for len(bestBid.Orders) > 0 && !order.IsFilled() {
			buyOrder := bestBid.Orders[0]
			trade := ob.executeTrade(buyOrder, order, bestBid.Price)
			trades = append(trades, trade)

			if buyOrder.IsFilled() {
				bestBid.Orders = bestBid.Orders[1:]
			}
		}

		if len(bestBid.Orders) == 0 {
			ob.bids = ob.bids[1:]
		}
	}

	if len(trades) > 0 && !order.IsFilled() {
		order.Status = StatusPartial
	} else if order.IsFilled() {
		order.Status = StatusFilled
	}

	return trades
}

func (ob *OrderBook) executeTrade(buyOrder, sellOrder *Order, price float64) *Trade {
	ob.tradeCounter++

	qty := buyOrder.Remaining()
	if sellOrder.Remaining() < qty {
		qty = sellOrder.Remaining()
	}

	buyOrder.Filled += qty
	sellOrder.Filled += qty

	if buyOrder.IsFilled() {
		buyOrder.Status = StatusFilled
	} else {
		buyOrder.Status = StatusPartial
	}
	if sellOrder.IsFilled() {
		sellOrder.Status = StatusFilled
	} else {
		sellOrder.Status = StatusPartial
	}

	return &Trade{
		ID:          fmt.Sprintf("trd_%d_%d", time.Now().UnixNano(), ob.tradeCounter),
		Symbol:      ob.Symbol,
		BuyOrderID:  buyOrder.ID,
		SellOrderID: sellOrder.ID,
		BuyerID:     buyOrder.UserID,
		SellerID:    sellOrder.UserID,
		Price:       price,
		Quantity:    qty,
		ExecutedAt:  time.Now(),
	}
}

func (ob *OrderBook) addToBook(order *Order) {
	if order.Side == SideBuy {
		ob.addToBids(order)
	} else {
		ob.addToAsks(order)
	}
}

func (ob *OrderBook) addToBids(order *Order) {
	for _, level := range ob.bids {
		if level.Price == order.Price {
			level.Orders = append(level.Orders, order)
			return
		}
	}
	ob.bids = append(ob.bids, &PriceLevel{
		Price:  order.Price,
		Orders: []*Order{order},
	})
	sort.Slice(ob.bids, func(i, j int) bool {
		return ob.bids[i].Price > ob.bids[j].Price
	})
}

func (ob *OrderBook) addToAsks(order *Order) {
	for _, level := range ob.asks {
		if level.Price == order.Price {
			level.Orders = append(level.Orders, order)
			return
		}
	}
	ob.asks = append(ob.asks, &PriceLevel{
		Price:  order.Price,
		Orders: []*Order{order},
	})
	sort.Slice(ob.asks, func(i, j int) bool {
		return ob.asks[i].Price < ob.asks[j].Price
	})
}

func (ob *OrderBook) Cancel(orderID string) bool {
	ob.mu.Lock()
	defer ob.mu.Unlock()

	for _, level := range ob.bids {
		for i, o := range level.Orders {
			if o.ID == orderID {
				o.Status = StatusCancelled
				level.Orders = append(level.Orders[:i], level.Orders[i+1:]...)
				return true
			}
		}
	}
	for _, level := range ob.asks {
		for i, o := range level.Orders {
			if o.ID == orderID {
				o.Status = StatusCancelled
				level.Orders = append(level.Orders[:i], level.Orders[i+1:]...)
				return true
			}
		}
	}
	return false
}

type BookSnapshot struct {
	Symbol string
	Bids   []LevelSnapshot
	Asks   []LevelSnapshot
}

type LevelSnapshot struct {
	Price    float64
	Quantity int64
}

func (ob *OrderBook) Snapshot() BookSnapshot {
	ob.mu.Lock()
	defer ob.mu.Unlock()

	snap := BookSnapshot{Symbol: ob.Symbol}

	for _, level := range ob.bids {
		snap.Bids = append(snap.Bids, LevelSnapshot{
			Price:    level.Price,
			Quantity: level.TotalQuantity(),
		})
	}
	for _, level := range ob.asks {
		snap.Asks = append(snap.Asks, LevelSnapshot{
			Price:    level.Price,
			Quantity: level.TotalQuantity(),
		})
	}
	return snap
}