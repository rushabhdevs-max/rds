// Mock Fetch Holdings API v2 response — Section 2.1 of spec
// holdings.quantity / holdings.averagePrice are NESTED under holdings object
// positions are SEPARATE from holdings (intraday/BTST vs delivery)
// API does NOT return current price or P&L — calculated from Bhavcopy CLOSE_PRICE

export const holdingsResponse = {
  success: true,
  data: {
    securities: [
      {
        nseTicker: "RELIANCE",
        bseTicker: "RELIANCE",
        isin: "INE002A01018",
        name: "Reliance Industries Ltd",
        holdings: { quantity: 10, averagePrice: 2450.5 },
        positions: {
          nse: { quantity: 2, averagePrice: 2480.0 },
          bse: { quantity: 0, averagePrice: 0 },
        },
        transactableQuantity: 12,
        smallcaseQuantity: 0,
      },
      {
        nseTicker: "INFY",
        bseTicker: "INFY",
        isin: "INE009A01021",
        name: "Infosys Ltd",
        holdings: { quantity: 25, averagePrice: 1380.75 },
        positions: {
          nse: { quantity: 0, averagePrice: 0 },
          bse: { quantity: 0, averagePrice: 0 },
        },
        transactableQuantity: 25,
        smallcaseQuantity: 5,
      },
      {
        nseTicker: "HDFCBANK",
        bseTicker: "HDFCBANK",
        isin: "INE040A01034",
        name: "HDFC Bank Ltd",
        holdings: { quantity: 15, averagePrice: 1520.3 },
        positions: {
          nse: { quantity: 1, averagePrice: 1545.0 },
          bse: { quantity: 0, averagePrice: 0 },
        },
        transactableQuantity: 16,
        smallcaseQuantity: 0,
      },
      {
        nseTicker: "TCS",
        bseTicker: "TCS",
        isin: "INE467B01029",
        name: "Tata Consultancy Services Ltd",
        holdings: { quantity: 8, averagePrice: 3520.0 },
        positions: {
          nse: { quantity: 0, averagePrice: 0 },
          bse: { quantity: 0, averagePrice: 0 },
        },
        transactableQuantity: 8,
        smallcaseQuantity: 0,
      },
      {
        nseTicker: "ADANIENT",
        bseTicker: "ADANIENT",
        isin: "INE423A01024",
        name: "Adani Enterprises Ltd",
        holdings: { quantity: 20, averagePrice: 2800.0 },
        positions: {
          nse: { quantity: 0, averagePrice: 0 },
          bse: { quantity: 0, averagePrice: 0 },
        },
        transactableQuantity: 20,
        smallcaseQuantity: 0,
      },
      {
        nseTicker: "J&KBANK",
        bseTicker: "J&KBANK",
        isin: "INE168A01041",
        name: "Jammu and Kashmir Bank Ltd",
        holdings: { quantity: 4, averagePrice: 36.68 },
        positions: {
          nse: { quantity: 1, averagePrice: 34.1 },
          bse: { quantity: 0, averagePrice: 0 },
        },
        transactableQuantity: 5,
        smallcaseQuantity: 2,
      },
      // ETFs (SERIES = MF in Bhavcopy)
      {
        nseTicker: "NIFTYBEES",
        bseTicker: "NIFTYBEES",
        isin: "INF204KB14I2",
        name: "Nippon India ETF Nifty BeES",
        holdings: { quantity: 50, averagePrice: 245.8 },
        positions: {
          nse: { quantity: 0, averagePrice: 0 },
          bse: { quantity: 0, averagePrice: 0 },
        },
        transactableQuantity: 50,
        smallcaseQuantity: 0,
      },
      {
        nseTicker: "GOLDBEES",
        bseTicker: "GOLDBEES",
        isin: "INF204KB17I5",
        name: "Nippon India ETF Gold BeES",
        holdings: { quantity: 100, averagePrice: 52.4 },
        positions: {
          nse: { quantity: 0, averagePrice: 0 },
          bse: { quantity: 0, averagePrice: 0 },
        },
        transactableQuantity: 100,
        smallcaseQuantity: 0,
      },
    ],
    snapshotDate: "2026-04-10T09:30:00.000Z",
    lastUpdate: "2026-04-10T09:35:12.000Z",
  },
};
