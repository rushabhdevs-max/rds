// Mock order webhook payloads — Section 2.3 of spec
// Real webhook data from spec for Screens 15-21
// Display rules: hide batchId, transactionId, smallcaseAuthId, checksum, exchangeOrderId, statusMessage
// broker: strip test suffix (e.g. "kite-leprechaun" → "Kite")

export function formatBrokerName(raw) {
  if (!raw) return "Broker";
  const base = raw.split("-")[0];
  return base.charAt(0).toUpperCase() + base.slice(1);
}

// Screen 15: Placed Regular — real webhook data
const placedRegular = {
  batchId: "63afcadb204dc65ef0c72862",
  buyAmount: 0,
  sellAmount: 0,
  quantity: 2,
  filled: 0,
  status: "PLACED",
  variety: "regular",
  completedDate: null,
  orders: [
    {
      status: "PLACED", quantity: 1, tradingsymbol: "RELIANCE",
      transactionType: "SELL", exchange: "NSE", orderType: "MARKET",
      product: "CNC", filledQuantity: 0, averagePrice: 0,
      exchangeOrderId: null, errorCode: null, statusMessage: null,
      price: 0, triggerPrice: 0,
    },
    {
      status: "PLACED", quantity: 1, tradingsymbol: "ADANIENT",
      transactionType: "BUY", exchange: "NSE", orderType: "MARKET",
      product: "CNC", filledQuantity: 0, averagePrice: 0,
      exchangeOrderId: null, errorCode: null, statusMessage: null,
      price: 0, triggerPrice: 0,
    },
  ],
  unplaced: [],
  transactionId: "TRX_59671f98a1b2c3d4e5f6a7b8",
  broker: "kite-leprechaun",
  smallcaseAuthId: "5ef33705f610f80b5453b319",
  timestamp: "2026-04-10T05:38:37.595Z",
  checksum: "f6609f15f0dd38eaf...",
};

// Screen 16: Placed AMO — real webhook data
const placedAMO = {
  batchId: "63afc98b204dc65ef0c72861",
  buyAmount: 0,
  sellAmount: 0,
  quantity: 1,
  filled: 0,
  status: "PLACED",
  variety: "amo",
  completedDate: null,
  orders: [
    {
      status: "PLACED", quantity: 1, tradingsymbol: "INFY",
      transactionType: "BUY", exchange: "NSE", orderType: "MARKET",
      product: "CNC", filledQuantity: 0, averagePrice: 0,
      exchangeOrderId: null, errorCode: null, statusMessage: null,
      price: 0, triggerPrice: 0,
    },
  ],
  unplaced: [],
  transactionId: "TRX_amo_1234567890",
  broker: "kite-leprechaun",
  smallcaseAuthId: "5ef33705f610f80b5453b319",
  timestamp: "2026-04-10T05:32:59.000Z",
  checksum: "a1b2c3d4e5f6...",
};

// Screen 17: Placed Limit/SL/SLM — real webhook data
const placedLimitSLSLM = {
  batchId: "63afc92e204dc65ef0c72860",
  buyAmount: 0,
  sellAmount: 0,
  quantity: 3,
  filled: 0,
  status: "PLACED",
  variety: "regular",
  completedDate: null,
  orders: [
    {
      status: "PLACED", quantity: 1, tradingsymbol: "INFY",
      transactionType: "SELL", exchange: "NSE", orderType: "SLM",
      product: "CNC", filledQuantity: 0, averagePrice: 0,
      exchangeOrderId: null, errorCode: null, statusMessage: null,
      price: 0, triggerPrice: 1500,
    },
    {
      status: "PLACED", quantity: 1, tradingsymbol: "CREDITACC",
      transactionType: "BUY", exchange: "NSE", orderType: "LIMIT",
      product: "CNC", filledQuantity: 0, averagePrice: 0,
      exchangeOrderId: null, errorCode: null, statusMessage: null,
      price: 900, triggerPrice: 0,
    },
    {
      status: "PLACED", quantity: 1, tradingsymbol: "RELIANCE",
      transactionType: "BUY", exchange: "NSE", orderType: "SL",
      product: "CNC", filledQuantity: 0, averagePrice: 0,
      exchangeOrderId: null, errorCode: null, statusMessage: null,
      price: 2610, triggerPrice: 2600,
    },
  ],
  unplaced: [],
  transactionId: "TRX_limit_sl_slm_001",
  broker: "kite-leprechaun",
  smallcaseAuthId: "5ef33705f610f80b5453b319",
  timestamp: "2026-04-10T04:15:22.000Z",
  checksum: "d4e5f6a7b8...",
};

// Screen 18: Completed — real webhook data (completion of Screen 15's order)
const completedOrder = {
  batchId: "63afcadb204dc65ef0c72862",
  buyAmount: 3858.25,
  sellAmount: 2547.14,
  quantity: 2,
  filled: 2,
  status: "COMPLETED",
  variety: "regular",
  completedDate: "2026-04-10T05:38:40.616Z",
  orders: [
    {
      status: "COMPLETE", quantity: 1, tradingsymbol: "RELIANCE",
      transactionType: "SELL", exchange: "NSE", orderType: "MARKET",
      product: "CNC", filledQuantity: 1, averagePrice: 2547.14,
      exchangeOrderId: "1234567890", errorCode: null, statusMessage: "NA",
      price: 0, triggerPrice: 0,
    },
    {
      status: "COMPLETE", quantity: 1, tradingsymbol: "ADANIENT",
      transactionType: "BUY", exchange: "NSE", orderType: "MARKET",
      product: "CNC", filledQuantity: 1, averagePrice: 3858.25,
      exchangeOrderId: "1234567891", errorCode: null, statusMessage: "NA",
      price: 0, triggerPrice: 0,
    },
  ],
  unplaced: [],
  transactionId: "TRX_59671f98a1b2c3d4e5f6a7b8",
  broker: "kite-leprechaun",
  smallcaseAuthId: "5ef33705f610f80b5453b319",
  timestamp: "2026-04-10T05:38:37.595Z",
  checksum: "f6609f15f0dd38eaf...",
};

// Screen 19: Unplaced/Error — real webhook data
const unplacedError = {
  batchId: "63afcbbb204dc65ef0c72863",
  buyAmount: 0,
  sellAmount: 0,
  quantity: 2,
  filled: 0,
  status: "UNPLACED",
  variety: "regular",
  completedDate: "2026-04-09T08:28:16.000Z",
  orders: [],
  unplaced: [
    {
      status: "ERROR", quantity: 1, tradingsymbol: "ITC",
      transactionType: "BUY", exchange: "NSE", orderType: "MARKET",
      product: "CNC", filledQuantity: 0, averagePrice: 0,
      exchangeOrderId: null, errorCode: "INSUFFICIENT_FUNDS",
      statusMessage: "NA", price: 0, triggerPrice: 0,
    },
    {
      status: "ERROR", quantity: 10, tradingsymbol: "RELIANCE",
      transactionType: "BUY", exchange: "NSE", orderType: "MARKET",
      product: "CNC", filledQuantity: 0, averagePrice: 0,
      exchangeOrderId: null, errorCode: "INSUFFICIENT_FUNDS",
      statusMessage: "NA", price: 0, triggerPrice: 0,
    },
  ],
  transactionId: "TRX_20e788abcdef",
  broker: "kite",
  smallcaseAuthId: "5ef33705f610f80b5453b319",
  timestamp: "2026-04-09T08:28:10.000Z",
  checksum: "e5f6a7b8c9...",
};

// Screen 20: Partial Fill — INFERRED (no real webhook, designed from docs)
const partialFill = {
  batchId: "63afcd00204dc65ef0c72864",
  buyAmount: 1442.30,
  sellAmount: 0,
  quantity: 2,
  filled: 1,
  status: "PARTIAL",
  variety: "regular",
  completedDate: null,
  orders: [
    {
      status: "COMPLETE", quantity: 1, tradingsymbol: "INFY",
      transactionType: "BUY", exchange: "NSE", orderType: "LIMIT",
      product: "CNC", filledQuantity: 1, averagePrice: 1442.30,
      exchangeOrderId: "9876543210", errorCode: null, statusMessage: "NA",
      price: 1445, triggerPrice: 0,
    },
    {
      status: "PLACED", quantity: 1, tradingsymbol: "HDFCBANK",
      transactionType: "BUY", exchange: "NSE", orderType: "LIMIT",
      product: "CNC", filledQuantity: 0, averagePrice: 0,
      exchangeOrderId: null, errorCode: null, statusMessage: null,
      price: 1550, triggerPrice: 0,
    },
  ],
  unplaced: [],
  transactionId: "TRX_partial_001",
  broker: "groww",
  smallcaseAuthId: "5ef33705f610f80b5453b319",
  timestamp: "2026-04-10T06:12:45.000Z",
  checksum: "partial123...",
  _inferred: true,
};

// Screen 21: Cancelled — INFERRED (no real webhook)
const cancelledRegular = {
  batchId: "63afce00204dc65ef0c72865",
  buyAmount: 0,
  sellAmount: 0,
  quantity: 1,
  filled: 0,
  status: "PLACED",
  variety: "regular",
  completedDate: null,
  orders: [
    {
      status: "CANCELLED", quantity: 1, tradingsymbol: "TATAMOTORS",
      transactionType: "BUY", exchange: "NSE", orderType: "LIMIT",
      product: "CNC", filledQuantity: 0, averagePrice: 0,
      exchangeOrderId: null, errorCode: null, statusMessage: null,
      price: 680, triggerPrice: 0,
    },
  ],
  unplaced: [],
  transactionId: "TRX_cancel_001",
  broker: "kite-leprechaun",
  smallcaseAuthId: "5ef33705f610f80b5453b319",
  timestamp: "2026-04-10T03:45:00.000Z",
  checksum: "cancel123...",
  _inferred: true,
};

const cancelledAMO = {
  batchId: "63afcf00204dc65ef0c72866",
  buyAmount: 0,
  sellAmount: 0,
  quantity: 1,
  filled: 0,
  status: "PLACED",
  variety: "amo",
  completedDate: null,
  orders: [
    {
      status: "CANCELLED AMO", quantity: 1, tradingsymbol: "SBIN",
      transactionType: "BUY", exchange: "NSE", orderType: "MARKET",
      product: "CNC", filledQuantity: 0, averagePrice: 0,
      exchangeOrderId: null, errorCode: null, statusMessage: null,
      price: 0, triggerPrice: 0,
    },
  ],
  unplaced: [],
  transactionId: "TRX_cancel_amo_001",
  broker: "groww",
  smallcaseAuthId: "5ef33705f610f80b5453b319",
  timestamp: "2026-04-09T16:10:00.000Z",
  checksum: "cancelamo123...",
  _inferred: true,
};

export const allOrders = [
  completedOrder,
  placedRegular,
  placedAMO,
  placedLimitSLSLM,
  partialFill,
  unplacedError,
  cancelledRegular,
  cancelledAMO,
];

// Status color mapping
export function getStatusColor(status) {
  switch (status) {
    case "COMPLETED": case "COMPLETE": return "#1D9E75";
    case "PLACED": return "#378ADD";
    case "PARTIAL": return "#E8440A";
    case "UNPLACED": case "ERROR": case "REJECTED": return "#D85A30";
    case "CANCELLED": case "CANCELLED AMO": return "#D85A30";
    default: return "#666";
  }
}

// Filter helpers
export function getOrderDisplayStatus(order) {
  if (order.status === "COMPLETED") return "Completed";
  if (order.status === "UNPLACED") return "Failed";
  if (order.status === "PARTIAL") return "Partial";
  // Check order-level cancellations
  const hasCancelled = [...order.orders, ...order.unplaced].some(
    o => o.status === "CANCELLED" || o.status === "CANCELLED AMO"
  );
  if (hasCancelled) return "Cancelled";
  if (order.variety === "amo") return "AMO · Placed";
  return "Placed";
}
