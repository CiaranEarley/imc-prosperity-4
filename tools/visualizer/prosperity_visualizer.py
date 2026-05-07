import csv
import json
import math
import re
import sys
import zipfile
from bisect import bisect_left
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

import pyqtgraph as pg
from PySide6.QtCore import Qt, Signal, QTimer, QRect
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QSplitter,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)


pg.setConfigOptions(antialias=False, background="w", foreground="k")
MAIN_LINE_WIDTH = 2.8
SECONDARY_LINE_WIDTH = 2.4
REFERENCE_LINE_WIDTH = 1.8


PRICE_FIELDS = [
    ("bid_price_1", "bid_volume_1"),
    ("bid_price_2", "bid_volume_2"),
    ("bid_price_3", "bid_volume_3"),
]
ASK_FIELDS = [
    ("ask_price_1", "ask_volume_1"),
    ("ask_price_2", "ask_volume_2"),
    ("ask_price_3", "ask_volume_3"),
]
DAY_TIMESTAMP_STRIDE = 1_000_000
MAX_AUTOLOAD_RUN_ARCHIVE_BYTES = 150_000_000
MAX_QUOTE_MARKERS_PER_SIDE = 6_000
POSITION_LIMITS = {
    "HYDROGEL_PACK": 200,
    "VELVETFRUIT_EXTRACT": 200,
    "VEV_4000": 300,
    "VEV_4500": 300,
    "VEV_5000": 300,
    "VEV_5100": 300,
    "VEV_5200": 300,
    "VEV_5300": 300,
    "VEV_5400": 300,
    "VEV_5500": 300,
    "VEV_6000": 300,
    "VEV_6500": 300,
}


@dataclass
class PriceRow:
    day: int
    timestamp: int
    global_ts: int
    product: str
    mid_price: float
    pnl: float
    bid_prices: List[Optional[float]]
    bid_volumes: List[float]
    ask_prices: List[Optional[float]]
    ask_volumes: List[float]
    best_bid: Optional[float]
    best_ask: Optional[float]
    wall_mid: Optional[float]


@dataclass
class TradeRow:
    day: int
    timestamp: int
    global_ts: int
    product: str
    price: float
    quantity: int
    buyer: str
    seller: str


@dataclass
class OwnFillRow:
    global_ts: int
    timestamp: int
    product: str
    price: float
    quantity: int
    side: str


@dataclass
class OwnQuoteRow:
    global_ts: int
    timestamp: int
    product: str
    price: float
    quantity: int
    side: str


def parse_float(raw: str) -> Optional[float]:
    if raw is None or raw == "":
        return None
    return float(raw)


def parse_price(raw: str) -> Optional[float]:
    value = parse_float(raw)
    if value is None or value <= 0:
        return None
    return value


def parse_int(raw: str) -> Optional[int]:
    if raw is None or raw == "":
        return None
    return int(float(raw))


class ProsperityDataset:
    def __init__(self) -> None:
        self.price_rows: Dict[str, List[PriceRow]] = defaultdict(list)
        self.trade_rows: Dict[str, List[TradeRow]] = defaultdict(list)
        self.products: List[str] = []

    def load_price_files(self, paths: List[Path]) -> None:
        self.price_rows.clear()
        for path in paths:
            with path.open("r", newline="") as handle:
                reader = csv.DictReader(handle, delimiter=";")
                for row in reader:
                    day = int(row["day"])
                    timestamp = int(row["timestamp"])
                    global_ts = day * DAY_TIMESTAMP_STRIDE + timestamp
                    product = row["product"]

                    bid_prices = [parse_price(row[p]) for p, _ in PRICE_FIELDS]
                    bid_volumes = [float(row[v]) if row[v] else 0.0 for _, v in PRICE_FIELDS]
                    ask_prices = [parse_price(row[p]) for p, _ in ASK_FIELDS]
                    ask_volumes = [float(row[v]) if row[v] else 0.0 for _, v in ASK_FIELDS]

                    valid_bids = [p for p in bid_prices if p is not None]
                    valid_asks = [p for p in ask_prices if p is not None]
                    best_bid = max(valid_bids) if valid_bids else None
                    best_ask = min(valid_asks) if valid_asks else None
                    wall_bid = min(valid_bids) if valid_bids else None
                    wall_ask = max(valid_asks) if valid_asks else None
                    wall_mid = None
                    if wall_bid is not None and wall_ask is not None:
                        wall_mid = (wall_bid + wall_ask) / 2.0

                    mid_price = parse_price(row["mid_price"])
                    if mid_price is None:
                        if best_bid is not None and best_ask is not None:
                            mid_price = (best_bid + best_ask) / 2.0
                        elif wall_mid is not None:
                            mid_price = wall_mid
                        elif best_bid is not None:
                            mid_price = best_bid
                        elif best_ask is not None:
                            mid_price = best_ask
                        else:
                            continue

                    price_row = PriceRow(
                        day=day,
                        timestamp=timestamp,
                        global_ts=global_ts,
                        product=product,
                        mid_price=mid_price,
                        pnl=float(row["profit_and_loss"]),
                        bid_prices=bid_prices,
                        bid_volumes=bid_volumes,
                        ask_prices=ask_prices,
                        ask_volumes=ask_volumes,
                        best_bid=best_bid,
                        best_ask=best_ask,
                        wall_mid=wall_mid,
                    )
                    self.price_rows[product].append(price_row)

        for product in self.price_rows:
            self.price_rows[product].sort(key=lambda r: r.global_ts)
        self._refresh_products()

    def load_trade_files(self, paths: List[Path]) -> None:
        self.trade_rows.clear()
        for path in paths:
            with path.open("r", newline="") as handle:
                reader = csv.DictReader(handle, delimiter=";")
                for row in reader:
                    timestamp = int(row["timestamp"])
                    day = self._infer_day_from_name(path.name)
                    global_ts = day * DAY_TIMESTAMP_STRIDE + timestamp
                    product = row["symbol"]
                    trade_row = TradeRow(
                        day=day,
                        timestamp=timestamp,
                        global_ts=global_ts,
                        product=product,
                        price=float(row["price"]),
                        quantity=int(float(row["quantity"])),
                        buyer=row["buyer"],
                        seller=row["seller"],
                    )
                    self.trade_rows[product].append(trade_row)

        for product in self.trade_rows:
            self.trade_rows[product].sort(key=lambda r: r.global_ts)
        self._refresh_products()

    def _infer_day_from_name(self, name: str) -> int:
        stem = Path(name).stem
        if "_day_" not in stem:
            return 0
        return int(stem.split("_day_")[-1])

    def _refresh_products(self) -> None:
        self.products = sorted(set(self.price_rows.keys()) | set(self.trade_rows.keys()))


class AxisAwareViewBox(pg.ViewBox):
    def wheelEvent(self, ev, axis=None):
        if axis is not None:
            super().wheelEvent(ev, axis=axis)
            return

        if not self.state["mouseEnabled"][0]:
            ev.ignore()
            return

        scale = 1.02 ** (ev.delta() * self.state["wheelScaleFactor"])
        center = pg.Point(pg.functions.invertQTransform(self.childGroup.transform()).map(ev.pos()))
        self._resetTarget()
        self.scaleBy([scale, 1.0], center)
        ev.accept()
        self.sigRangeChangedManually.emit([True, False])


class BasePlotWidget(pg.PlotWidget):
    doubleClicked = Signal(object)

    def __init__(self) -> None:
        super().__init__(viewBox=AxisAwareViewBox())
        self.showGrid(x=True, y=True, alpha=0.18)
        self.getAxis("left").setWidth(85)
        self.getAxis("right").setStyle(showValues=False)
        self.showAxis("right")

    def mouseDoubleClickEvent(self, event) -> None:
        self.doubleClicked.emit(self)
        super().mouseDoubleClickEvent(event)


class OrderBookPlot(BasePlotWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setLabel("left", "Price")
        self.setLabel("bottom", "Continuous Timestamp (day * 1,000,000 + ts)")
        self.addLegend(offset=(10, 10))


class TimeSeriesPlot(BasePlotWidget):
    def __init__(self, left_label: str) -> None:
        super().__init__()
        self.setLabel("left", left_label)
        self.setLabel("bottom", "Global Timestamp")


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Prosperity Order Book Visualizer")
        self.resize(1600, 980)
        self.app_root = self.resolve_app_root()
        self.icon_path = self.resolve_icon_path()
        if self.icon_path is not None:
            self.setWindowIcon(QIcon(str(self.icon_path)))

        self.dataset = ProsperityDataset()
        self.current_price_rows: List[PriceRow] = []
        self.current_trade_rows: List[TradeRow] = []
        self.own_fills_by_product: Dict[str, List[OwnFillRow]] = defaultdict(list)
        self.own_quotes_by_product: Dict[str, List[OwnQuoteRow]] = defaultdict(list)
        self.strategy_price_rows: Dict[str, List[PriceRow]] = defaultdict(list)
        self.strategy_timestamp_scale = 1
        self.strategy_has_fill_data = False
        self.strategy_has_quote_data = False
        self.strategy_source_label = "None"
        self.strategy_final_positions: Dict[str, int] = {}
        self.strategy_run_profit: Optional[float] = None
        self.strategy_submission_id: Optional[str] = None
        self.strategy_graph_points: List[tuple[int, float]] = []

        self.price_paths: List[Path] = []
        self.trade_paths: List[Path] = []
        self.strategy_log_path: Optional[Path] = None
        self.settings_path = self.app_root / "settings.json"
        self.saved_product = ""
        self.detached_windows: List[QMainWindow] = []
        self._startup_layout_fixed = False
        self._startup_layout_passes = 0
        self._last_view_signature = None
        self._row_ts_cache: Dict[tuple, List[int]] = {}

        self._build_ui()
        self._build_menu()
        self.load_settings()
        self.reload_inputs_from_folders()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if not self._startup_layout_fixed:
            self._startup_layout_fixed = True
            QTimer.singleShot(0, self.force_real_maximize)
            QTimer.singleShot(150, self.fix_startup_layout)
            QTimer.singleShot(600, self.fix_startup_layout)
            QTimer.singleShot(850, self.auto_range_main_views)

    def force_real_maximize(self) -> None:
        screen = self.screen() or QApplication.primaryScreen()
        if screen is not None:
            available = screen.availableGeometry()
            self.setGeometry(QRect(available))
        self.setWindowState((self.windowState() & ~Qt.WindowFullScreen) | Qt.WindowMaximized)
        self.raise_()
        self.activateWindow()

    def fix_startup_layout(self) -> None:
        if not self.isVisible():
            return
        self._startup_layout_passes += 1
        self.apply_splitter_sizes()
        self.centralWidget().layout().activate()
        self.activate_tab_layouts()
        self.apply_splitter_sizes()
        self.centralWidget().adjustSize()
        self.tabs.updateGeometry()
        self.tabs.repaint()
        self.updateGeometry()
        self.repaint()

    def apply_splitter_sizes(self) -> None:
        if not hasattr(self, "main_splitter"):
            return
        total_width = max(self.width(), 1600)
        left_width = max(420, min(520, int(total_width * 0.24)))
        right_width = max(1000, total_width - left_width)
        self.main_splitter.setSizes([left_width, right_width])

    def activate_tab_layouts(self) -> None:
        for index in range(self.tabs.count()):
            tab = self.tabs.widget(index)
            layout = tab.layout()
            if layout is not None:
                layout.activate()
            tab.updateGeometry()

    def _build_menu(self) -> None:
        file_menu = self.menuBar().addMenu("&File")

        refresh_action = QAction("Refresh", self)
        refresh_action.triggered.connect(self.reload_inputs_from_folders)
        file_menu.addAction(refresh_action)

        load_run_action = QAction("Load Run Archive...", self)
        load_run_action.triggered.connect(self.choose_strategy_log)
        file_menu.addAction(load_run_action)

    def choose_strategy_log(self) -> None:
        run_info_dir = self.app_root / "Run Information"
        path_text, _ = QFileDialog.getOpenFileName(
            self,
            "Load Run Archive",
            str(run_info_dir if run_info_dir.exists() else self.app_root),
            "Run archives (*.zip *.json *.log);;All files (*.*)",
        )
        if not path_text:
            return
        self.load_strategy_log(Path(path_text))
        self.refresh_product_combo()
        self.refresh_view()

    def _build_ui(self) -> None:
        root = QWidget()
        self.setCentralWidget(root)
        layout = QHBoxLayout(root)

        splitter = QSplitter(Qt.Horizontal)
        splitter.setChildrenCollapsible(False)
        layout.addWidget(splitter)
        self.main_splitter = splitter

        left_container = QWidget()
        left_container.setMinimumWidth(420)
        left_container.setMaximumWidth(560)
        left_container_layout = QVBoxLayout(left_container)
        left_container_layout.setContentsMargins(0, 0, 0, 0)
        left_scroll = QScrollArea()
        left_scroll.setWidgetResizable(True)
        left_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        left_scroll.setFrameShape(QScrollArea.NoFrame)
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_scroll.setWidget(left_panel)
        left_container_layout.addWidget(left_scroll)
        splitter.addWidget(left_container)
        self.left_scroll = left_scroll
        self.left_container = left_container

        control_box = QGroupBox("Controls")
        control_layout = QFormLayout(control_box)

        self.product_combo = QComboBox()
        self.product_combo.currentTextChanged.connect(self.refresh_view)
        control_layout.addRow("Product", self.product_combo)

        self.normalize_combo = QComboBox()
        self.normalize_combo.addItems(["None", "Mid Price", "Wall Mid", "Best Bid", "Best Ask"])
        self.normalize_combo.currentTextChanged.connect(self.refresh_view)
        control_layout.addRow("Normalize By", self.normalize_combo)

        self.overlay_combo = QComboBox()
        self.overlay_combo.addItems(
            [
                "None",
                "Spread",
                "Residual",
                "Top Depth Imbalance",
                "Rolling Mid (20)",
                "Rolling Wall Mid (20)",
                "Rolling Residual Mean (50)",
                "Rolling Residual Z-Score (50)",
            ]
        )
        self.overlay_combo.currentTextChanged.connect(self.refresh_view)
        control_layout.addRow("Indicator Overlay", self.overlay_combo)

        self.show_orderbook_check = QCheckBox("Show Order Book Levels")
        self.show_orderbook_check.setChecked(True)
        self.show_orderbook_check.stateChanged.connect(self.refresh_view)
        control_layout.addRow(self.show_orderbook_check)

        self.show_mid_check = QCheckBox("Show Mid / Indicators")
        self.show_mid_check.setChecked(True)
        self.show_mid_check.stateChanged.connect(self.refresh_view)
        control_layout.addRow(self.show_mid_check)

        self.show_trades_check = QCheckBox("Show Public Trades")
        self.show_trades_check.setChecked(True)
        self.show_trades_check.stateChanged.connect(self.refresh_view)
        control_layout.addRow(self.show_trades_check)

        self.trade_min_spin = QSpinBox()
        self.trade_min_spin.setRange(0, 100000)
        self.trade_min_spin.setValue(0)
        self.trade_min_spin.valueChanged.connect(self.refresh_view)
        control_layout.addRow("Trade Min Qty", self.trade_min_spin)

        self.trade_max_spin = QSpinBox()
        self.trade_max_spin.setRange(0, 100000)
        self.trade_max_spin.setValue(100000)
        self.trade_max_spin.valueChanged.connect(self.refresh_view)
        control_layout.addRow("Trade Max Qty", self.trade_max_spin)

        self.downsample_spin = QSpinBox()
        self.downsample_spin.setRange(1, 200)
        self.downsample_spin.setValue(1)
        self.downsample_spin.valueChanged.connect(self.refresh_view)
        control_layout.addRow("Downsample", self.downsample_spin)

        self.large_edge_spin = QSpinBox()
        self.large_edge_spin.setRange(1, 50)
        self.large_edge_spin.setValue(5)
        self.large_edge_spin.valueChanged.connect(self.refresh_view)
        control_layout.addRow("Large Edge Threshold", self.large_edge_spin)

        self.save_preset_button = QPushButton("Save Preset")
        self.save_preset_button.clicked.connect(self.save_settings)
        control_layout.addRow(self.save_preset_button)

        self.reload_preset_button = QPushButton("Reload Preset")
        self.reload_preset_button.clicked.connect(self.load_settings_and_refresh)
        control_layout.addRow(self.reload_preset_button)

        left_layout.addWidget(control_box)

        help_box = QGroupBox("Help")
        help_layout = QVBoxLayout(help_box)
        self.zoom_tip_label = QLabel(
            "Zoom tip: wheel inside chart = x zoom only.\n"
            "Use the left price axis wheel or drag for y zoom.\n"
            "Click legend color samples to hide/show series."
        )
        self.zoom_tip_label.setWordWrap(True)
        self.zoom_tip_label.setMinimumHeight(72)
        help_layout.addWidget(self.zoom_tip_label)

        stats_box = QGroupBox("Hovered Timestamp")
        stats_layout = QVBoxLayout(stats_box)
        self.hover_label = QLabel("Load files to inspect data.")
        self.hover_label.setWordWrap(True)
        self.hover_label.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        stats_layout.addWidget(self.hover_label)

        summary_box = QGroupBox("Summary")
        summary_layout = QVBoxLayout(summary_box)
        self.summary_label = QLabel("No dataset loaded.")
        self.summary_label.setWordWrap(True)
        summary_layout.addWidget(self.summary_label)

        info_tabs = QTabWidget()
        info_tabs.setDocumentMode(True)
        info_tabs.addTab(help_box, "Help")
        info_tabs.addTab(stats_box, "Hover")
        info_tabs.addTab(summary_box, "Summary")
        left_layout.addWidget(info_tabs)
        self.info_tabs = info_tabs
        left_layout.addStretch(1)

        right_panel = QWidget()
        right_panel.setMinimumWidth(900)
        right_layout = QVBoxLayout(right_panel)
        splitter.addWidget(right_panel)

        self.tabs = QTabWidget()
        right_layout.addWidget(self.tabs)

        orderbook_tab = QWidget()
        orderbook_layout = QVBoxLayout(orderbook_tab)
        self.orderbook_plot = OrderBookPlot()
        self.indicator_plot = TimeSeriesPlot("Value")
        self.spread_plot = TimeSeriesPlot("Spread / Trade Qty")
        orderbook_layout.addWidget(self.orderbook_plot, stretch=6)
        orderbook_layout.addWidget(self.indicator_plot, stretch=2)
        orderbook_layout.addWidget(self.spread_plot, stretch=2)
        self.tabs.addTab(orderbook_tab, "Order Book")

        spread_tab = QWidget()
        spread_layout = QVBoxLayout(spread_tab)
        self.spread_analysis_plot = TimeSeriesPlot("Spread / Mean")
        self.spread_residual_plot = TimeSeriesPlot("Residual / Z-Score")
        spread_layout.addWidget(self.spread_analysis_plot, stretch=2)
        spread_layout.addWidget(self.spread_residual_plot, stretch=2)
        self.tabs.addTab(spread_tab, "Spreads")

        smile_tab = QWidget()
        smile_layout = QVBoxLayout(smile_tab)
        self.smile_plot = TimeSeriesPlot("Value")
        self.smile_status_label = QLabel("Load option-like products to populate the smile view.")
        self.smile_status_label.setWordWrap(True)
        smile_layout.addWidget(self.smile_plot, stretch=3)
        smile_layout.addWidget(self.smile_status_label, stretch=0)
        self.tabs.addTab(smile_tab, "Vol Smile")

        autocorr_tab = QWidget()
        autocorr_layout = QVBoxLayout(autocorr_tab)
        self.autocorr_plot = TimeSeriesPlot("Autocorrelation")
        self.autocorr_status_label = QLabel("Autocorrelation of returns across lags.")
        self.autocorr_status_label.setWordWrap(True)
        autocorr_layout.addWidget(self.autocorr_plot, stretch=3)
        autocorr_layout.addWidget(self.autocorr_status_label, stretch=0)
        self.tabs.addTab(autocorr_tab, "Autocorr")

        inventory_tab = QWidget()
        inventory_layout = QVBoxLayout(inventory_tab)
        self.inventory_plot = TimeSeriesPlot("Inventory")
        self.inventory_status_label = QLabel("Inventory from own fills for the selected product.")
        self.inventory_status_label.setWordWrap(True)
        inventory_layout.addWidget(self.inventory_plot, stretch=3)
        inventory_layout.addWidget(self.inventory_status_label, stretch=0)
        self.tabs.addTab(inventory_tab, "Inventory")

        pnl_tab = QWidget()
        pnl_layout = QVBoxLayout(pnl_tab)
        self.pnl_plot = TimeSeriesPlot("PnL")
        self.pnl_status_label = QLabel("Per-product PnL and combined run PnL.")
        self.pnl_status_label.setWordWrap(True)
        pnl_layout.addWidget(self.pnl_plot, stretch=3)
        pnl_layout.addWidget(self.pnl_status_label, stretch=0)
        self.tabs.addTab(pnl_tab, "PnL")

        risk_tab = QWidget()
        risk_layout = QVBoxLayout(risk_tab)
        self.drawdown_plot = TimeSeriesPlot("Drawdown")
        self.underwater_plot = TimeSeriesPlot("Underwater")
        self.risk_status_label = QLabel("Drawdown depth and time spent below prior PnL highs.")
        self.risk_status_label.setWordWrap(True)
        risk_layout.addWidget(self.drawdown_plot, stretch=2)
        risk_layout.addWidget(self.underwater_plot, stretch=2)
        risk_layout.addWidget(self.risk_status_label, stretch=0)
        self.tabs.addTab(risk_tab, "Risk")

        rolling_tab = QWidget()
        rolling_layout = QVBoxLayout(rolling_tab)
        rolling_controls = QHBoxLayout()
        rolling_controls.addWidget(QLabel("Window"))
        self.rolling_window_spin = QSpinBox()
        self.rolling_window_spin.setRange(5, 2000)
        self.rolling_window_spin.setValue(100)
        self.rolling_window_spin.setSingleStep(25)
        self.rolling_window_spin.valueChanged.connect(self.refresh_view)
        rolling_controls.addWidget(self.rolling_window_spin)
        rolling_controls.addStretch(1)
        self.period_return_plot = TimeSeriesPlot("Period PnL")
        self.rolling_sharpe_plot = TimeSeriesPlot("Rolling Sharpe / Win Rate")
        self.rolling_status_label = QLabel("Rolling period returns and rolling risk-adjusted performance.")
        self.rolling_status_label.setWordWrap(True)
        rolling_layout.addLayout(rolling_controls)
        rolling_layout.addWidget(self.period_return_plot, stretch=2)
        rolling_layout.addWidget(self.rolling_sharpe_plot, stretch=2)
        rolling_layout.addWidget(self.rolling_status_label, stretch=0)
        self.tabs.addTab(rolling_tab, "Rolling")

        execution_tab = QWidget()
        execution_layout = QVBoxLayout(execution_tab)
        self.fill_edge_plot = TimeSeriesPlot("Fill Edge")
        self.cumulative_edge_plot = TimeSeriesPlot("Cumulative Edge")
        self.execution_status_label = QLabel("Fill edge versus wall mid or mid for the selected product.")
        self.execution_status_label.setWordWrap(True)
        execution_layout.addWidget(self.fill_edge_plot, stretch=2)
        execution_layout.addWidget(self.cumulative_edge_plot, stretch=2)
        execution_layout.addWidget(self.execution_status_label, stretch=0)
        self.tabs.addTab(execution_tab, "Execution")

        trades_tab = QWidget()
        trades_layout = QVBoxLayout(trades_tab)
        self.trades_table = QTableWidget()
        self.trades_table.setColumnCount(8)
        self.trades_table.setHorizontalHeaderLabels(["Timestamp", "Side", "Qty", "Price", "Fair", "Edge", "Edge x Qty", "Inventory"])
        self.trades_table.setSortingEnabled(True)
        self.trades_table.verticalHeader().setVisible(False)
        self.trades_status_label = QLabel("Own fill log for the selected product.")
        self.trades_status_label.setWordWrap(True)
        trades_layout.addWidget(self.trades_table, stretch=1)
        trades_layout.addWidget(self.trades_status_label, stretch=0)
        self.tabs.addTab(trades_tab, "Trades")

        self.stats_card_defs = [
            ("score", "Run Score", "Composite 0-100 score blending PnL, Sharpe, Sortino, Calmar, profit factor, win rate, drawdown, and time underwater."),
            ("total_pnl", "Total PnL", "Final PnL for the selected product."),
            ("sharpe", "Sharpe", "Mean PnL change divided by standard deviation, scaled to the run's PnL sampling cadence."),
            ("sortino", "Sortino", "Mean PnL change divided by downside deviation, scaled to the run's PnL sampling cadence."),
            ("calmar", "Calmar", "Total PnL divided by maximum drawdown."),
            ("win_rate", "Win Rate", "Share of non-zero PnL changes that are positive."),
            ("max_dd", "Max DD", "Maximum drawdown as a percentage of the best positive PnL peak."),
            ("max_dd_abs", "Max DD Abs", "Largest absolute peak-to-trough PnL drawdown."),
            ("underwater_pct", "DD Time", "Share of PnL samples that were below the previous peak."),
            ("cvar_95", "CVaR 95%", "Average of the worst 5% PnL changes."),
            ("profit_factor", "Profit Factor", "Gross positive PnL changes divided by gross negative PnL changes."),
            ("expectancy", "Expectancy", "Average non-zero PnL change per PnL observation."),
            ("best_step", "Best Step", "Largest single-sample PnL increase."),
            ("worst_step", "Worst Step", "Largest single-sample PnL decrease."),
            ("skewness", "Skewness", "Skewness of PnL changes."),
            ("data_points", "Data Points", "Number of PnL observations used."),
            ("fill_count", "Fills", "Number of own fills for the selected product."),
            ("gross_volume", "Gross Vol", "Total own filled quantity for the selected product."),
            ("avg_fill_edge", "Avg Fill Edge", "Quantity-weighted fill edge versus wall mid or mid. Buys use fair - price; sells use price - fair."),
            ("quote_count", "Quotes", "Number of own quote orders parsed from LambdaLog."),
            ("quote_fill_rate", "Fill/Quote", "Own fill events divided by logged own quote orders. This is approximate because partial fills can split."),
            ("max_inventory", "Max Inv", "Maximum absolute inventory reconstructed from own fills."),
            ("inv_utilization", "Inv Util", "Maximum absolute inventory as a percentage of the known position limit."),
        ]
        stats_tab = self.create_stats_panel(
            labels_attr="stats_value_labels",
            cards_attr="stats_cards",
            status_attr="stats_status_label",
            status_text="Load a strategy run to calculate PnL statistics.",
        )
        self.tabs.addTab(stats_tab, "Stats")
        combined_stats_tab = self.create_stats_panel(
            labels_attr="combined_stats_value_labels",
            cards_attr="combined_stats_cards",
            status_attr="combined_stats_status_label",
            status_text="Load a strategy run to calculate combined script statistics.",
        )
        self.tabs.addTab(combined_stats_tab, "Combined Stats")

        self.orderbook_plot.scene().sigMouseMoved.connect(self.on_mouse_moved)
        self.indicator_plot.setXLink(self.orderbook_plot)
        self.spread_plot.setXLink(self.orderbook_plot)
        self.spread_analysis_plot.setXLink(self.orderbook_plot)
        self.spread_residual_plot.setXLink(self.orderbook_plot)
        self.inventory_plot.setXLink(self.orderbook_plot)
        self.pnl_plot.setXLink(self.orderbook_plot)
        self.drawdown_plot.setXLink(self.orderbook_plot)
        self.underwater_plot.setXLink(self.orderbook_plot)
        self.period_return_plot.setXLink(self.orderbook_plot)
        self.rolling_sharpe_plot.setXLink(self.orderbook_plot)
        self.fill_edge_plot.setXLink(self.orderbook_plot)
        self.cumulative_edge_plot.setXLink(self.orderbook_plot)

        self.plot_registry = {
            "orderbook": self.orderbook_plot,
            "indicator": self.indicator_plot,
            "spread": self.spread_plot,
            "spread_analysis": self.spread_analysis_plot,
            "spread_residual": self.spread_residual_plot,
            "smile": self.smile_plot,
            "autocorr": self.autocorr_plot,
            "inventory": self.inventory_plot,
            "pnl": self.pnl_plot,
            "drawdown": self.drawdown_plot,
            "underwater": self.underwater_plot,
            "period_return": self.period_return_plot,
            "rolling_sharpe": self.rolling_sharpe_plot,
            "fill_edge": self.fill_edge_plot,
            "cumulative_edge": self.cumulative_edge_plot,
        }
        for plot_key, plot_widget in self.plot_registry.items():
            plot_widget.plot_key = plot_key
            plot_widget.doubleClicked.connect(self.open_detached_plot)

        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        self.apply_splitter_sizes()

    def create_stats_panel(
        self,
        labels_attr: str,
        cards_attr: str,
        status_attr: str,
        status_text: str,
    ) -> QWidget:
        stats_tab = QWidget()
        stats_outer_layout = QVBoxLayout(stats_tab)
        stats_scroll = QScrollArea()
        stats_scroll.setWidgetResizable(True)
        stats_scroll.setFrameShape(QScrollArea.NoFrame)
        stats_content = QWidget()
        stats_layout = QVBoxLayout(stats_content)
        stats_grid = QGridLayout()
        stats_grid.setHorizontalSpacing(18)
        stats_grid.setVerticalSpacing(18)

        value_labels: Dict[str, QLabel] = {}
        cards: Dict[str, QGroupBox] = {}
        for idx, (key, title, tooltip) in enumerate(self.stats_card_defs):
            card = QGroupBox(title)
            card.setToolTip(tooltip)
            card_layout = QVBoxLayout(card)
            value_label = QLabel("N/A")
            value_font = value_label.font()
            value_font.setPointSize(26 if key == "score" else 22)
            value_font.setBold(key == "score")
            value_label.setFont(value_font)
            value_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            card_layout.addWidget(value_label)
            value_labels[key] = value_label
            cards[key] = card
            stats_grid.addWidget(card, idx // 3, idx % 3)

        stats_layout.addLayout(stats_grid)
        status_label = QLabel(status_text)
        status_label.setWordWrap(True)
        stats_layout.addWidget(status_label)
        stats_layout.addStretch(1)
        stats_scroll.setWidget(stats_content)
        stats_outer_layout.addWidget(stats_scroll)

        setattr(self, labels_attr, value_labels)
        setattr(self, cards_attr, cards)
        setattr(self, status_attr, status_label)
        return stats_tab

    def clear_strategy_log(self) -> None:
        self.strategy_log_path = None
        self.own_fills_by_product = defaultdict(list)
        self.own_quotes_by_product = defaultdict(list)
        self.strategy_price_rows = defaultdict(list)
        self._row_ts_cache.clear()
        self.strategy_timestamp_scale = 1
        self.strategy_has_fill_data = False
        self.strategy_has_quote_data = False
        self.strategy_source_label = "None"
        self.strategy_final_positions = {}
        self.strategy_run_profit = None
        self.strategy_submission_id = None
        self.strategy_graph_points = []

    def reload_inputs_from_folders(self) -> None:
        self.dataset = ProsperityDataset()
        self._row_ts_cache.clear()
        self.price_paths = []
        self.trade_paths = []
        self.clear_strategy_log()
        price_dir = self.app_root / "Price & Trade Data"
        if price_dir.exists():
            price_paths = sorted(price_dir.glob("prices_round_*_day_*.csv"))
            trade_paths = sorted(price_dir.glob("trades_round_*_day_*.csv"))
            if price_paths:
                self.price_paths = price_paths
                self.dataset.load_price_files(price_paths)
            if trade_paths:
                self.trade_paths = trade_paths
                self.dataset.load_trade_files(trade_paths)

        run_info_dir = self.app_root / "Run Information"
        if run_info_dir.exists():
            run_archives = sorted(run_info_dir.glob("*.zip"), key=lambda p: p.stat().st_mtime, reverse=True)
            auto_archives = [
                archive
                for archive in run_archives
                if archive.stat().st_size <= MAX_AUTOLOAD_RUN_ARCHIVE_BYTES
            ]
            if auto_archives:
                self.load_strategy_log(auto_archives[0])
            elif run_archives:
                self.load_strategy_log(run_archives[0])

        self._last_view_signature = None
        self.refresh_product_combo()
        self.refresh_view()
        QTimer.singleShot(0, self.auto_range_main_views)

    def read_strategy_payload(self, path: Path) -> dict:
        if path.suffix.lower() == ".zip":
            with zipfile.ZipFile(path, "r") as archive:
                json_entries = [entry for entry in archive.namelist() if entry.lower().endswith(".json")]
                log_entries = [entry for entry in archive.namelist() if entry.lower().endswith(".log")]
                candidates = log_entries + json_entries
                if not candidates:
                    raise ValueError(f"No json/log payload found inside {path.name}")
                best_payload = None
                best_score = -1
                parsed_payloads = []
                for target_name in candidates:
                    with archive.open(target_name, "r") as handle:
                        text = handle.read().decode("utf-8", errors="replace")
                    payload = json.loads(text)
                    parsed_payloads.append(payload)
                    score = 0
                    if payload.get("activitiesLog"):
                        score += 1
                    if payload.get("tradeHistory"):
                        score += 2
                    if payload.get("logs"):
                        score += 2
                    if isinstance(payload.get("graphLog"), str) and payload.get("graphLog"):
                        score += 1
                    if score > best_score:
                        best_payload = payload
                        best_score = score
                if best_payload is None:
                    raise ValueError(f"Could not parse a usable payload inside {path.name}")
                merged_payload = dict(best_payload)
                for payload in parsed_payloads:
                    for key, value in payload.items():
                        if key not in merged_payload or merged_payload.get(key) in (None, "", [], {}):
                            merged_payload[key] = value
                return merged_payload
        return json.loads(path.read_text(encoding="utf-8"))

    def load_strategy_log(self, path: Path) -> None:
        obj = self.read_strategy_payload(path)
        self.strategy_log_path = path
        self.own_fills_by_product = defaultdict(list)
        self.own_quotes_by_product = defaultdict(list)
        self.strategy_price_rows = defaultdict(list)
        self.strategy_has_fill_data = False
        self.strategy_has_quote_data = False
        self.strategy_source_label = f"Run archive ({path.name})" if path.suffix.lower() == ".zip" else path.name
        self.strategy_final_positions = {}
        self.strategy_run_profit = None
        self.strategy_submission_id = None
        self.strategy_graph_points = []

        positions = obj.get("positions", [])
        if isinstance(positions, list):
            for entry in positions:
                if isinstance(entry, dict) and entry.get("symbol") not in (None, ""):
                    try:
                        self.strategy_final_positions[str(entry["symbol"])] = int(entry.get("quantity", 0))
                    except Exception:
                        continue

        try:
            if obj.get("profit") is not None:
                self.strategy_run_profit = float(obj.get("profit"))
        except Exception:
            self.strategy_run_profit = None

        submission_id = obj.get("submissionId")
        if isinstance(submission_id, str) and submission_id:
            self.strategy_submission_id = submission_id

        day_offset = 0
        timestamp_scale = 1
        activities_log = obj.get("activitiesLog", "")
        if activities_log:
            try:
                reader = list(csv.DictReader(activities_log.splitlines(), delimiter=";"))
                days = sorted({int(row["day"]) for row in reader if row.get("day") not in (None, "")})
                if len(days) == 1:
                    day_offset = days[0]
                activity_timestamps = [
                    int(row["timestamp"])
                    for row in reader
                    if row.get("timestamp") not in (None, "")
                ]
                price_max_ts = 0
                if self.dataset.price_rows:
                    price_max_ts = max(
                        row.timestamp
                        for rows in self.dataset.price_rows.values()
                        for row in rows
                    )
                if activity_timestamps and price_max_ts > 0:
                    activity_max_ts = max(activity_timestamps)
                    if activity_max_ts > 0:
                        ratio = price_max_ts / activity_max_ts
                        rounded_ratio = round(ratio)
                        if rounded_ratio >= 2 and abs(ratio - rounded_ratio) <= 0.25:
                            timestamp_scale = rounded_ratio

                for row in reader:
                    if row.get("product") in (None, "") or row.get("timestamp") in (None, ""):
                        continue

                    day = int(row["day"])
                    raw_timestamp = int(row["timestamp"])
                    scaled_timestamp = raw_timestamp * timestamp_scale
                    global_ts = day * DAY_TIMESTAMP_STRIDE + scaled_timestamp
                    product = row["product"]

                    bid_prices = [parse_price(row[p]) for p, _ in PRICE_FIELDS]
                    bid_volumes = [float(row[v]) if row[v] else 0.0 for _, v in PRICE_FIELDS]
                    ask_prices = [parse_price(row[p]) for p, _ in ASK_FIELDS]
                    ask_volumes = [float(row[v]) if row[v] else 0.0 for _, v in ASK_FIELDS]

                    valid_bids = [p for p in bid_prices if p is not None]
                    valid_asks = [p for p in ask_prices if p is not None]
                    best_bid = max(valid_bids) if valid_bids else None
                    best_ask = min(valid_asks) if valid_asks else None
                    wall_bid = min(valid_bids) if valid_bids else None
                    wall_ask = max(valid_asks) if valid_asks else None
                    wall_mid = None
                    if wall_bid is not None and wall_ask is not None:
                        wall_mid = (wall_bid + wall_ask) / 2.0

                    mid_price = parse_price(row.get("mid_price", ""))
                    if mid_price is None:
                        if best_bid is not None and best_ask is not None:
                            mid_price = (best_bid + best_ask) / 2.0
                        elif best_bid is not None:
                            mid_price = best_bid
                        elif best_ask is not None:
                            mid_price = best_ask
                        else:
                            continue

                    pnl = float(row.get("profit_and_loss", "0") or 0.0)

                    self.strategy_price_rows[product].append(
                        PriceRow(
                            day=day,
                            timestamp=scaled_timestamp,
                            global_ts=global_ts,
                            product=product,
                            mid_price=mid_price,
                            pnl=pnl,
                            bid_prices=bid_prices,
                            bid_volumes=bid_volumes,
                            ask_prices=ask_prices,
                            ask_volumes=ask_volumes,
                            best_bid=best_bid,
                            best_ask=best_ask,
                            wall_mid=wall_mid,
                        )
                    )
            except Exception:
                day_offset = 0
                timestamp_scale = 1

        graph_log = obj.get("graphLog", "")
        if isinstance(graph_log, str) and graph_log.strip():
            try:
                reader = csv.DictReader(graph_log.splitlines(), delimiter=";")
                for row in reader:
                    if row.get("timestamp") in (None, "") or row.get("value") in (None, ""):
                        continue
                    raw_timestamp = int(float(row["timestamp"]))
                    scaled_timestamp = raw_timestamp * timestamp_scale
                    global_ts = day_offset * DAY_TIMESTAMP_STRIDE + scaled_timestamp if abs(scaled_timestamp) < DAY_TIMESTAMP_STRIDE else scaled_timestamp
                    self.strategy_graph_points.append((global_ts, float(row["value"])))
                self.strategy_graph_points.sort(key=lambda item: item[0])
            except Exception:
                self.strategy_graph_points = []

        self.strategy_timestamp_scale = timestamp_scale
        for product in self.strategy_price_rows:
            self.strategy_price_rows[product].sort(key=lambda row: row.global_ts)

        trade_history = obj.get("tradeHistory", [])
        if trade_history:
            self.strategy_has_fill_data = True
        for trade in trade_history:
            side = None
            if trade.get("buyer") == "SUBMISSION":
                side = "BUY"
            elif trade.get("seller") == "SUBMISSION":
                side = "SELL"
            if side is None:
                continue

            timestamp = int(trade["timestamp"]) * timestamp_scale
            global_ts = timestamp
            if abs(timestamp) < DAY_TIMESTAMP_STRIDE:
                global_ts = day_offset * DAY_TIMESTAMP_STRIDE + timestamp

            fill = OwnFillRow(
                global_ts=global_ts,
                timestamp=timestamp,
                product=trade["symbol"],
                price=float(trade["price"]),
                quantity=int(trade["quantity"]),
                side=side,
            )
            self.own_fills_by_product[fill.product].append(fill)

        for product in self.own_fills_by_product:
            self.own_fills_by_product[product].sort(key=lambda fill: fill.global_ts)

        logs = obj.get("logs", [])
        if logs:
            self.strategy_has_quote_data = True
        for log_entry in logs:
            lambda_log = log_entry.get("lambdaLog", "") or ""
            if not lambda_log:
                continue

            for line in lambda_log.splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    parsed = json.loads(line)
                except Exception:
                    continue

                if not isinstance(parsed, dict) or parsed.get("kind") != "quotes":
                    continue

                product = parsed.get("product")
                orders = parsed.get("orders", [])
                raw_timestamp = parsed.get("timestamp", log_entry.get("timestamp"))
                if product in (None, "") or raw_timestamp in (None, ""):
                    continue

                timestamp = int(raw_timestamp) * timestamp_scale
                global_ts = timestamp
                if abs(timestamp) < DAY_TIMESTAMP_STRIDE:
                    global_ts = day_offset * DAY_TIMESTAMP_STRIDE + timestamp

                for order in orders:
                    if not isinstance(order, (list, tuple)) or len(order) < 2:
                        continue
                    price = float(order[0])
                    quantity = int(order[1])
                    side = "BUY" if quantity > 0 else "SELL"
                    self.own_quotes_by_product[product].append(
                        OwnQuoteRow(
                            global_ts=global_ts,
                            timestamp=timestamp,
                            product=product,
                            price=price,
                            quantity=abs(quantity),
                            side=side,
                        )
                    )

        for product in self.own_quotes_by_product:
            self.own_quotes_by_product[product].sort(key=lambda quote: quote.global_ts)
        self._row_ts_cache.clear()

    def refresh_product_combo(self) -> None:
        current = self.saved_product or self.product_combo.currentText()
        available_products = sorted(set(self.dataset.products) | set(self.strategy_price_rows.keys()))
        self.product_combo.blockSignals(True)
        self.product_combo.clear()
        self.product_combo.addItems(available_products)
        if current and current in available_products:
            self.product_combo.setCurrentText(current)
        elif available_products:
            self.product_combo.setCurrentIndex(0)
        self.product_combo.blockSignals(False)

    def refresh_view(self) -> None:
        product = self.product_combo.currentText()
        if not product:
            self.clear_plots()
            return

        view_signature = self.current_view_signature()
        should_refit = view_signature != self._last_view_signature

        self.current_price_rows = self.dataset.price_rows.get(product, [])
        if not self.current_price_rows:
            self.current_price_rows = self.strategy_price_rows.get(product, [])
        self.current_trade_rows = self.dataset.trade_rows.get(product, [])

        if not self.current_price_rows:
            self.clear_plots()
            self.summary_label.setText(f"No price rows loaded for {product}.")
            return

        step = max(1, self.downsample_spin.value())
        price_rows = self.current_price_rows[::step]

        self.render_orderbook(product, price_rows)
        self.render_indicator_panel(product, price_rows)
        self.render_spread_panel(product, price_rows)
        self.render_spread_analysis_tab(product, price_rows)
        self.render_smile_tab()
        self.render_autocorr_tab(product, price_rows)
        self.render_inventory_tab(product, price_rows)
        self.render_pnl_tab(product, price_rows)
        self.render_risk_tab(product, self.current_price_rows)
        self.render_rolling_tab(product, self.current_price_rows)
        self.render_execution_tab(product, self.current_price_rows)
        self.render_trades_tab(product, self.current_price_rows)
        self.render_stats_tab(product, self.current_price_rows)
        self.render_combined_stats_tab()
        self.update_summary(product, price_rows)
        self.save_settings()
        self._last_view_signature = view_signature

    def clear_plots(self) -> None:
        self.orderbook_plot.clear()
        self.indicator_plot.clear()
        self.spread_plot.clear()
        self.spread_analysis_plot.clear()
        self.spread_residual_plot.clear()
        self.smile_plot.clear()
        self.autocorr_plot.clear()
        self.inventory_plot.clear()
        self.pnl_plot.clear()
        self.drawdown_plot.clear()
        self.underwater_plot.clear()
        self.period_return_plot.clear()
        self.rolling_sharpe_plot.clear()
        self.fill_edge_plot.clear()
        self.cumulative_edge_plot.clear()
        if hasattr(self, "trades_table"):
            self.trades_table.setRowCount(0)
        self.clear_stats_tab()
        self.clear_combined_stats_tab()

    def clear_stats_tab(self) -> None:
        if not hasattr(self, "stats_value_labels"):
            return
        for label in self.stats_value_labels.values():
            label.setText("N/A")
        self.stats_status_label.setText("No PnL stats available.")

    def clear_combined_stats_tab(self) -> None:
        if not hasattr(self, "combined_stats_value_labels"):
            return
        for label in self.combined_stats_value_labels.values():
            label.setText("N/A")
        self.combined_stats_status_label.setText("No combined PnL stats available.")

    def current_view_signature(self) -> tuple:
        return (
            self.product_combo.currentText(),
            self.normalize_combo.currentText(),
            self.downsample_spin.value(),
            self.rolling_window_spin.value() if hasattr(self, "rolling_window_spin") else 100,
            self.tabs.currentIndex(),
        )

    def auto_range_main_views(self) -> None:
        plots = [
            self.orderbook_plot,
            self.indicator_plot,
            self.spread_plot,
            self.spread_analysis_plot,
            self.spread_residual_plot,
            self.inventory_plot,
            self.pnl_plot,
            self.drawdown_plot,
            self.underwater_plot,
            self.period_return_plot,
            self.rolling_sharpe_plot,
            self.fill_edge_plot,
            self.cumulative_edge_plot,
        ]
        for plot in plots:
            try:
                plot.plotItem.autoBtnClicked()
            except Exception:
                pass

    def ensure_legend(self, plot: pg.PlotWidget) -> None:
        if plot.plotItem.legend is None:
            plot.addLegend(offset=(10, 10))
            legend = plot.plotItem.legend
            legend.sigSampleClicked.connect(lambda item, p=plot: self.on_legend_sample_clicked(p, item))
        if not hasattr(plot, "_legend_target_map"):
            plot._legend_target_map = {}

    def resolve_icon_path(self) -> Optional[Path]:
        candidates = [
            self.app_root / "VisualiserIcon.ico",
            self.app_root / "visualisericon.ico",
            self.app_root / "visualiser_icon.ico",
        ]
        for candidate in candidates:
            if candidate.exists():
                return candidate
        return None

    def resolve_app_root(self) -> Path:
        if getattr(sys, "frozen", False):
            return Path(sys.executable).resolve().parent
        return Path(__file__).resolve().parent.parent

    def on_legend_sample_clicked(self, plot: pg.PlotWidget, proxy_item) -> None:
        targets = getattr(plot, "_legend_target_map", {}).get(proxy_item, [])
        visible = proxy_item.isVisible()
        for target in targets:
            target.setVisible(visible)

    def add_legend_sample(self, plot: pg.PlotWidget, name: str, targets=None, pen=None, symbol=None, symbol_brush=None) -> None:
        proxy = plot.plot(
            [math.nan],
            [math.nan],
            pen=pen,
            symbol=symbol,
            symbolSize=8 if symbol else None,
            symbolBrush=symbol_brush,
            symbolPen=pen,
            name=name,
        )
        proxy.setVisible(True)
        if targets:
            plot._legend_target_map[proxy] = targets

    def clone_plot_items(self, source: pg.PlotWidget, target: pg.PlotWidget) -> None:
        target.clear()
        source_item = source.getPlotItem()
        target_item = target.getPlotItem()

        target.showGrid(x=True, y=True, alpha=0.18)
        target.setTitle(source_item.titleLabel.text)
        left_label = source_item.getAxis("left").labelText or ""
        bottom_label = source_item.getAxis("bottom").labelText or ""
        if left_label:
            target.setLabel("left", left_label)
        if bottom_label:
            target.setLabel("bottom", bottom_label)

        if source_item.legend is not None and target_item.legend is None:
            target.addLegend(offset=(10, 10))

        for item in source_item.items:
            if isinstance(item, pg.PlotDataItem):
                x, y = item.getData()
                if x is None or y is None:
                    continue
                target.plot(
                    x,
                    y,
                    pen=item.opts.get("pen"),
                    symbol=item.opts.get("symbol"),
                    symbolSize=item.opts.get("symbolSize"),
                    symbolBrush=item.opts.get("symbolBrush"),
                    symbolPen=item.opts.get("symbolPen"),
                    name=item.name(),
                )
            elif isinstance(item, pg.ScatterPlotItem):
                x, y = item.getData()
                if x is None or y is None:
                    continue
                scatter = pg.ScatterPlotItem(
                    x=x,
                    y=y,
                    size=item.opts.get("size", 7),
                    symbol=item.opts.get("symbol", "o"),
                    brush=item.opts.get("brush"),
                    pen=item.opts.get("pen"),
                    name=item.name(),
                )
                target.addItem(scatter)
            elif isinstance(item, pg.BarGraphItem):
                opts = item.opts
                target.addItem(
                    pg.BarGraphItem(
                        x=opts.get("x"),
                        x0=opts.get("x0"),
                        x1=opts.get("x1"),
                        height=opts.get("height"),
                        width=opts.get("width"),
                        brush=opts.get("brush"),
                        pen=opts.get("pen"),
                    )
                )
            elif isinstance(item, pg.InfiniteLine):
                target.addItem(
                    pg.InfiniteLine(
                        pos=item.value(),
                        angle=item.angle,
                        pen=item.pen,
                    )
                )

        x_range, y_range = source.viewRange()
        target.setXRange(x_range[0], x_range[1], padding=0)
        target.setYRange(y_range[0], y_range[1], padding=0)

    def open_detached_plot(self, source_plot: pg.PlotWidget) -> None:
        window = QMainWindow(self)
        window.resize(1400, 900)
        if self.icon_path is not None:
            window.setWindowIcon(QIcon(str(self.icon_path)))
        detached_plot = OrderBookPlot() if getattr(source_plot, "plot_key", "") == "orderbook" else TimeSeriesPlot(
            source_plot.getPlotItem().getAxis("left").labelText or "Value"
        )
        detached_plot.setBackground("w")
        self.clone_plot_items(source_plot, detached_plot)
        window.setCentralWidget(detached_plot)
        window.setWindowTitle(f"Prosperity Visualiser - {source_plot.getPlotItem().titleLabel.text}")
        window.showMaximized()
        self.detached_windows.append(window)

    def settings_payload(self) -> dict:
        return {
            "product": self.product_combo.currentText(),
            "normalize": self.normalize_combo.currentText(),
            "overlay": self.overlay_combo.currentText(),
            "show_orderbook": self.show_orderbook_check.isChecked(),
            "show_mid": self.show_mid_check.isChecked(),
            "show_trades": self.show_trades_check.isChecked(),
            "trade_min": self.trade_min_spin.value(),
            "trade_max": self.trade_max_spin.value(),
            "downsample": self.downsample_spin.value(),
            "large_edge_threshold": self.large_edge_spin.value(),
            "tab_index": self.tabs.currentIndex(),
            "strategy_log_path": str(self.strategy_log_path) if self.strategy_log_path else "",
        }

    def save_settings(self) -> None:
        try:
            self.settings_path.write_text(json.dumps(self.settings_payload(), indent=2))
        except Exception:
            pass

    def load_settings(self) -> None:
        if not self.settings_path.exists():
            return
        try:
            payload = json.loads(self.settings_path.read_text())
        except Exception:
            return
        self.saved_product = payload.get("product", "")
        self.normalize_combo.setCurrentText(payload.get("normalize", "None"))
        self.overlay_combo.setCurrentText(payload.get("overlay", "None"))
        self.show_orderbook_check.setChecked(payload.get("show_orderbook", True))
        self.show_mid_check.setChecked(payload.get("show_mid", True))
        self.show_trades_check.setChecked(payload.get("show_trades", True))
        self.trade_min_spin.setValue(payload.get("trade_min", 0))
        self.trade_max_spin.setValue(payload.get("trade_max", 100000))
        self.downsample_spin.setValue(payload.get("downsample", 1))
        self.large_edge_spin.setValue(payload.get("large_edge_threshold", 5))
        self.tabs.setCurrentIndex(payload.get("tab_index", 0))

    def load_settings_and_refresh(self) -> None:
        self.load_settings()
        if self.saved_product and self.saved_product in self.dataset.products:
            self.product_combo.setCurrentText(self.saved_product)
        self.refresh_view()

    def normalizer_value(self, row: PriceRow) -> float:
        choice = self.normalize_combo.currentText()
        if choice == "Mid Price":
            return row.mid_price
        if choice == "Wall Mid":
            return row.wall_mid if row.wall_mid is not None else row.mid_price
        if choice == "Best Bid":
            return row.best_bid if row.best_bid is not None else row.mid_price
        if choice == "Best Ask":
            return row.best_ask if row.best_ask is not None else row.mid_price
        return 0.0

    def normalize_price(self, price: Optional[float], row: PriceRow) -> Optional[float]:
        if price is None:
            return None
        return price - self.normalizer_value(row)

    def render_orderbook(self, product: str, rows: List[PriceRow]) -> None:
        self.orderbook_plot.clear()
        self.ensure_legend(self.orderbook_plot)
        self.orderbook_plot.setTitle(f"{product} Order Book")
        bid_palette = [(25, 90, 255), (65, 135, 255), (120, 175, 255)]
        ask_palette = [(255, 50, 50), (255, 105, 85), (255, 160, 120)]

        if self.show_orderbook_check.isChecked():
            for level_idx in range(3):
                bid_x, bid_y, bid_sizes = [], [], []
                ask_x, ask_y, ask_sizes = [], [], []
                for row in rows:
                    bid_price = self.normalize_price(row.bid_prices[level_idx], row)
                    ask_price = self.normalize_price(row.ask_prices[level_idx], row)
                    if bid_price is not None:
                        bid_x.append(row.global_ts)
                        bid_y.append(bid_price)
                        bid_sizes.append(max(5.0, min(24.0, 5.0 + math.sqrt(abs(row.bid_volumes[level_idx])) * 2.0)))
                    if ask_price is not None:
                        ask_x.append(row.global_ts)
                        ask_y.append(ask_price)
                        ask_sizes.append(max(5.0, min(24.0, 5.0 + math.sqrt(abs(row.ask_volumes[level_idx])) * 2.0)))

                if bid_x:
                    scatter = pg.ScatterPlotItem(
                        x=bid_x,
                        y=bid_y,
                        size=bid_sizes,
                        brush=pg.mkBrush(*bid_palette[level_idx], 170),
                        pen=pg.mkPen(*bid_palette[level_idx], 100),
                        name=f"Bid L{level_idx + 1}",
                    )
                    self.orderbook_plot.addItem(scatter)

                if ask_x:
                    scatter = pg.ScatterPlotItem(
                        x=ask_x,
                        y=ask_y,
                        size=ask_sizes,
                        brush=pg.mkBrush(*ask_palette[level_idx], 170),
                        pen=pg.mkPen(*ask_palette[level_idx], 100),
                        name=f"Ask L{level_idx + 1}",
                    )
                    self.orderbook_plot.addItem(scatter)

        if self.show_mid_check.isChecked():
            x = [row.global_ts for row in rows]
            mid_y = [self.normalize_price(row.mid_price, row) or 0.0 for row in rows]
            wall_y = [
                self.normalize_price(row.wall_mid, row) if row.wall_mid is not None else math.nan
                for row in rows
            ]
            self.orderbook_plot.plot(x, mid_y, pen=pg.mkPen("k", width=MAIN_LINE_WIDTH), name="Mid")
            self.orderbook_plot.plot(x, wall_y, pen=pg.mkPen((255, 165, 0), width=SECONDARY_LINE_WIDTH), name="Wall Mid")

        if self.show_trades_check.isChecked() and self.current_trade_rows:
            min_qty = self.trade_min_spin.value()
            max_qty = self.trade_max_spin.value()
            trade_x, trade_y, trade_sizes = [], [], []
            for trade in self.current_trade_rows:
                if not (min_qty <= trade.quantity <= max_qty):
                    continue
                row = self.find_row_at_ts(rows, trade.global_ts)
                trade_x.append(trade.global_ts)
                trade_y.append(trade.price - self.normalizer_value(row))
                trade_sizes.append(max(7.0, min(20.0, 6.0 + math.sqrt(abs(trade.quantity)) * 1.8)))

            if trade_x:
                scatter = pg.ScatterPlotItem(
                    x=trade_x,
                    y=trade_y,
                    size=trade_sizes,
                    symbol="x",
                    pen=pg.mkPen(255, 170, 0, width=1.8),
                    brush=None,
                    name="Public Trades",
                )
                self.orderbook_plot.addItem(scatter)

        own_fills = self.own_fills_by_product.get(product, [])
        if own_fills:
            buy_x, buy_y, sell_x, sell_y = [], [], [], []
            fill_reference_rows = self.strategy_price_rows.get(product, rows)
            for fill in own_fills:
                row = self.find_row_at_ts(fill_reference_rows, fill.global_ts)
                normalized_price = fill.price - self.normalizer_value(row)
                if fill.side == "BUY":
                    buy_x.append(fill.global_ts)
                    buy_y.append(normalized_price)
                else:
                    sell_x.append(fill.global_ts)
                    sell_y.append(normalized_price)

            if buy_x:
                self.orderbook_plot.addItem(
                    pg.ScatterPlotItem(
                        x=buy_x,
                        y=buy_y,
                        size=11,
                        symbol="t1",
                        brush=pg.mkBrush(30, 180, 60, 220),
                        pen=pg.mkPen(20, 120, 40, width=1.4),
                        name="Own Buys",
                    )
                )
            if sell_x:
                self.orderbook_plot.addItem(
                    pg.ScatterPlotItem(
                        x=sell_x,
                        y=sell_y,
                        size=11,
                        symbol="t",
                        brush=pg.mkBrush(190, 40, 40, 220),
                        pen=pg.mkPen(130, 20, 20, width=1.4),
                        name="Own Sells",
                    )
                )

        own_quotes = self.own_quotes_by_product.get(product, [])
        if own_quotes:
            best_bid_quotes: Dict[int, OwnQuoteRow] = {}
            best_ask_quotes: Dict[int, OwnQuoteRow] = {}
            for quote in own_quotes:
                if quote.side == "BUY":
                    current = best_bid_quotes.get(quote.global_ts)
                    if current is None or quote.price > current.price:
                        best_bid_quotes[quote.global_ts] = quote
                else:
                    current = best_ask_quotes.get(quote.global_ts)
                    if current is None or quote.price < current.price:
                        best_ask_quotes[quote.global_ts] = quote

            quote_buy_x, quote_buy_y, quote_sell_x, quote_sell_y = [], [], [], []
            quote_reference_rows = self.strategy_price_rows.get(product, rows)
            bid_values = sorted(best_bid_quotes.values(), key=lambda q: q.global_ts)
            ask_values = sorted(best_ask_quotes.values(), key=lambda q: q.global_ts)
            bid_step = max(1, math.ceil(len(bid_values) / MAX_QUOTE_MARKERS_PER_SIDE))
            ask_step = max(1, math.ceil(len(ask_values) / MAX_QUOTE_MARKERS_PER_SIDE))

            for quote in bid_values[::bid_step]:
                row = self.find_row_at_ts(quote_reference_rows, quote.global_ts)
                normalized_price = quote.price - self.normalizer_value(row)
                quote_buy_x.append(quote.global_ts)
                quote_buy_y.append(normalized_price)

            for quote in ask_values[::ask_step]:
                row = self.find_row_at_ts(quote_reference_rows, quote.global_ts)
                normalized_price = quote.price - self.normalizer_value(row)
                quote_sell_x.append(quote.global_ts)
                quote_sell_y.append(normalized_price)

            if quote_buy_x:
                self.orderbook_plot.addItem(
                    pg.ScatterPlotItem(
                        x=quote_buy_x,
                        y=quote_buy_y,
                        size=8,
                        symbol="star",
                        brush=pg.mkBrush(0, 0, 0, 220),
                        pen=pg.mkPen(0, 0, 0, width=1.0),
                        name="Our Bid Quotes",
                    )
                )
            if quote_sell_x:
                self.orderbook_plot.addItem(
                    pg.ScatterPlotItem(
                        x=quote_sell_x,
                        y=quote_sell_y,
                        size=8,
                        symbol="star",
                        brush=pg.mkBrush(40, 40, 40, 220),
                        pen=pg.mkPen(0, 0, 0, width=1.0),
                        name="Our Ask Quotes",
                    )
                )

    def render_indicator_panel(self, product: str, rows: List[PriceRow]) -> None:
        self.indicator_plot.clear()
        self.ensure_legend(self.indicator_plot)
        self.indicator_plot.setTitle("Derived Indicators")

        x = [row.global_ts for row in rows]
        spread = [
            (row.best_ask - row.best_bid) if row.best_ask is not None and row.best_bid is not None else math.nan
            for row in rows
        ]
        residual = [row.mid_price - (row.wall_mid if row.wall_mid is not None else row.mid_price) for row in rows]
        self.indicator_plot.plot(x, spread, pen=pg.mkPen((110, 110, 110), width=1.2), name="Spread")
        self.indicator_plot.plot(x, spread, pen=pg.mkPen((110, 110, 110), width=SECONDARY_LINE_WIDTH), name="Spread")
        self.indicator_plot.plot(x, residual, pen=pg.mkPen((255, 140, 0), width=SECONDARY_LINE_WIDTH), name="Mid - WallMid")

        overlay_name = self.overlay_combo.currentText()
        overlay_series = self.compute_overlay_series(rows, overlay_name)
        if overlay_series is not None:
            self.indicator_plot.plot(
                x,
                overlay_series,
                pen=pg.mkPen((130, 50, 220), width=MAIN_LINE_WIDTH),
                name=overlay_name,
            )

    def render_spread_panel(self, product: str, rows: List[PriceRow]) -> None:
        self.spread_plot.clear()
        self.ensure_legend(self.spread_plot)
        self.spread_plot.setTitle("Trade Flow / Depth")

        x = [row.global_ts for row in rows]
        top_depth = []
        for row in rows:
            bid_depth = row.bid_volumes[0] if row.bid_prices[0] is not None else 0.0
            ask_depth = row.ask_volumes[0] if row.ask_prices[0] is not None else 0.0
            top_depth.append(bid_depth - ask_depth)

        self.spread_plot.plot(x, top_depth, pen=pg.mkPen((0, 120, 0), width=SECONDARY_LINE_WIDTH), name="Top Depth Imbalance")

        if self.current_trade_rows:
            min_qty = self.trade_min_spin.value()
            max_qty = self.trade_max_spin.value()
            per_ts = defaultdict(int)
            for trade in self.current_trade_rows:
                if min_qty <= trade.quantity <= max_qty:
                    per_ts[trade.global_ts] += trade.quantity
            trade_x = sorted(per_ts.keys())
            trade_y = [per_ts[t] for t in trade_x]
            bars = pg.BarGraphItem(x=trade_x, height=trade_y, width=70, brush=(160, 100, 255, 120))
            self.spread_plot.addItem(bars)

    def rolling_mean(self, values: List[float], window: int) -> List[float]:
        out: List[float] = []
        queue: List[float] = []
        running = 0.0
        for value in values:
            queue.append(value)
            running += value
            if len(queue) > window:
                running -= queue.pop(0)
            out.append(running / len(queue))
        return out

    def rolling_std(self, values: List[float], window: int) -> List[float]:
        out: List[float] = []
        queue: List[float] = []
        for value in values:
            queue.append(value)
            if len(queue) > window:
                queue.pop(0)
            mean_value = sum(queue) / len(queue)
            variance = sum((x - mean_value) ** 2 for x in queue) / max(1, len(queue))
            out.append(math.sqrt(variance))
        return out

    def compute_overlay_series(self, rows: List[PriceRow], overlay_name: str) -> Optional[List[float]]:
        if overlay_name == "None":
            return None

        mid = [row.mid_price for row in rows]
        wall = [row.wall_mid if row.wall_mid is not None else row.mid_price for row in rows]
        spread = [
            (row.best_ask - row.best_bid) if row.best_ask is not None and row.best_bid is not None else math.nan
            for row in rows
        ]
        depth_imbalance = []
        for row in rows:
            bid_depth = row.bid_volumes[0] if row.bid_prices[0] is not None else 0.0
            ask_depth = row.ask_volumes[0] if row.ask_prices[0] is not None else 0.0
            depth_imbalance.append(bid_depth - ask_depth)
        residual = [m - w for m, w in zip(mid, wall)]

        if overlay_name == "Spread":
            return spread
        if overlay_name == "Residual":
            return residual
        if overlay_name == "Top Depth Imbalance":
            return depth_imbalance
        if overlay_name == "Rolling Mid (20)":
            return self.rolling_mean(mid, 20)
        if overlay_name == "Rolling Wall Mid (20)":
            return self.rolling_mean(wall, 20)
        if overlay_name == "Rolling Residual Mean (50)":
            return self.rolling_mean(residual, 50)
        if overlay_name == "Rolling Residual Z-Score (50)":
            mean_series = self.rolling_mean(residual, 50)
            std_series = self.rolling_std(residual, 50)
            return [0.0 if s <= 1e-9 else (v - m) / s for v, m, s in zip(residual, mean_series, std_series)]
        return None

    def build_inventory_series(self, rows: List[PriceRow], fills: List[OwnFillRow]) -> List[int]:
        inventory_series: List[int] = []
        fill_idx = 0
        inventory = 0
        current_day = None
        sorted_fills = sorted(fills, key=lambda fill: fill.global_ts)
        for row in rows:
            row_day = row.global_ts // DAY_TIMESTAMP_STRIDE
            if row_day != current_day:
                inventory = 0
                current_day = row_day

            while fill_idx < len(sorted_fills) and sorted_fills[fill_idx].global_ts <= row.global_ts:
                fill = sorted_fills[fill_idx]
                fill_day = fill.global_ts // DAY_TIMESTAMP_STRIDE
                if fill_day < row_day:
                    fill_idx += 1
                    continue
                if fill_day > row_day:
                    break
                inventory += fill.quantity if fill.side == "BUY" else -fill.quantity
                fill_idx += 1
            inventory_series.append(inventory)
        return inventory_series

    def build_inventory_path(self, rows: List[PriceRow], fills: List[OwnFillRow]) -> tuple[List[int], List[int]]:
        if not rows:
            return [], []

        sorted_fills = sorted(fills, key=lambda fill: fill.global_ts)
        rows_by_day: Dict[int, List[PriceRow]] = defaultdict(list)
        fills_by_day: Dict[int, List[OwnFillRow]] = defaultdict(list)
        for row in rows:
            rows_by_day[row.global_ts // DAY_TIMESTAMP_STRIDE].append(row)
        for fill in sorted_fills:
            fills_by_day[fill.global_ts // DAY_TIMESTAMP_STRIDE].append(fill)

        x_vals: List[int] = []
        y_vals: List[int] = []
        for day in sorted(rows_by_day):
            day_rows = rows_by_day[day]
            start_ts = day_rows[0].global_ts
            end_ts = day_rows[-1].global_ts
            inventory = 0

            if not x_vals or x_vals[-1] != start_ts - 1:
                x_vals.append(start_ts - 1)
                y_vals.append(0)
            else:
                y_vals[-1] = 0

            for fill in fills_by_day.get(day, []):
                if fill.global_ts < start_ts or fill.global_ts > end_ts:
                    continue
                if x_vals[-1] != fill.global_ts:
                    x_vals.append(fill.global_ts)
                    y_vals.append(inventory)
                inventory += fill.quantity if fill.side == "BUY" else -fill.quantity
                x_vals.append(fill.global_ts)
                y_vals.append(inventory)

            if x_vals[-1] != end_ts:
                x_vals.append(end_ts)
                y_vals.append(inventory)

        return x_vals, y_vals

    def build_step_series(self, x_vals: List[int], y_vals: List[int]) -> tuple[List[int], List[int]]:
        if not x_vals or not y_vals:
            return [], []
        if len(x_vals) != len(y_vals):
            n = min(len(x_vals), len(y_vals))
            x_vals = x_vals[:n]
            y_vals = y_vals[:n]

        step_x: List[int] = [x_vals[0]]
        step_y: List[int] = [y_vals[0]]
        for idx in range(1, len(x_vals)):
            step_x.append(x_vals[idx])
            step_y.append(y_vals[idx - 1])
            step_x.append(x_vals[idx])
            step_y.append(y_vals[idx])
        return step_x, step_y

    def render_inventory_tab(self, product: str, rows: List[PriceRow]) -> None:
        self.inventory_plot.clear()
        self.ensure_legend(self.inventory_plot)
        self.inventory_plot.setTitle(f"{product} Inventory")

        fills = self.own_fills_by_product.get(product, [])
        final_position = self.strategy_final_positions.get(product)
        if not fills:
            if final_position is None:
                self.inventory_status_label.setText("No own fill history available for this product.")
            else:
                self.inventory_status_label.setText(
                    f"No fill-by-fill history available for this product. Final reported position: {final_position}"
                )
            return

        x_vals, inventory_vals = self.build_inventory_path(rows, fills)
        if x_vals and inventory_vals:
            step_x, step_y = self.build_step_series(x_vals, inventory_vals)
            self.inventory_plot.plot(
                step_x,
                step_y,
                pen=pg.mkPen((0, 90, 220), width=MAIN_LINE_WIDTH),
                name="Inventory",
            )

        buy_x = [fill.global_ts for fill in fills if fill.side == "BUY"]
        buy_y = []
        sell_x = [fill.global_ts for fill in fills if fill.side == "SELL"]
        sell_y = []
        running_inventory = 0
        marker_day = None
        for fill in fills:
            fill_day = fill.global_ts // DAY_TIMESTAMP_STRIDE
            if fill_day != marker_day:
                running_inventory = 0
                marker_day = fill_day
            running_inventory += fill.quantity if fill.side == "BUY" else -fill.quantity
            if fill.side == "BUY":
                buy_y.append(running_inventory)
            else:
                sell_y.append(running_inventory)

        if buy_x:
            self.inventory_plot.addItem(
                pg.ScatterPlotItem(
                    x=buy_x,
                    y=buy_y,
                    size=10,
                    symbol="t1",
                    brush=pg.mkBrush(30, 180, 60, 220),
                    pen=pg.mkPen(20, 120, 40, width=1.2),
                    name="Buy Fills",
                )
            )
        if sell_x:
            self.inventory_plot.addItem(
                pg.ScatterPlotItem(
                    x=sell_x,
                    y=sell_y,
                    size=10,
                    symbol="t",
                    brush=pg.mkBrush(190, 40, 40, 220),
                    pen=pg.mkPen(130, 20, 20, width=1.2),
                    name="Sell Fills",
                )
            )

        min_inventory = min(inventory_vals) if inventory_vals else 0
        max_inventory = max(inventory_vals) if inventory_vals else 0
        final_inventory = inventory_vals[-1] if inventory_vals else 0
        final_position_text = "Unknown" if final_position is None else str(final_position)
        self.inventory_status_label.setText(
            f"Inventory path from own fills. Min: {min_inventory}, Max: {max_inventory}, "
            f"Final path: {final_inventory}, Final reported position: {final_position_text}"
        )

    def build_combined_pnl_series(self) -> tuple[List[int], List[float]]:
        all_rows: List[PriceRow] = []
        source_rows = self.strategy_price_rows if self.strategy_price_rows else self.dataset.price_rows
        for rows in source_rows.values():
            all_rows.extend(rows)
        if not all_rows:
            return [], []

        all_rows.sort(key=lambda row: (row.global_ts, row.product))
        latest_by_product: Dict[str, float] = {}
        combined_x: List[int] = []
        combined_y: List[float] = []
        for row in all_rows:
            latest_by_product[row.product] = row.pnl
            combined_x.append(row.global_ts)
            combined_y.append(sum(latest_by_product.values()))
        return combined_x, combined_y

    def combined_pnl_series_for_stats(self) -> tuple[List[int], List[float], str]:
        if self.strategy_graph_points:
            points = sorted(self.strategy_graph_points)
            return [point[0] for point in points], [point[1] for point in points], "run graphLog"

        combined_x, combined_y = self.build_combined_pnl_series()
        source = "reconstructed from product rows" if combined_x else "no combined PnL"
        return combined_x, combined_y, source

    def render_pnl_tab(self, product: str, rows: List[PriceRow]) -> None:
        self.pnl_plot.clear()
        self.ensure_legend(self.pnl_plot)
        self.pnl_plot.setTitle("PnL")

        x = [row.global_ts for row in rows]
        product_pnl = [row.pnl for row in rows]
        if x:
            self.pnl_plot.plot(
                x,
                product_pnl,
                pen=pg.mkPen((0, 90, 220), width=MAIN_LINE_WIDTH),
                name=f"{product} PnL",
            )

        combined_x: List[int] = []
        combined_y: List[float] = []
        combined_x, combined_y, source_text = self.combined_pnl_series_for_stats()

        if combined_x:
            self.pnl_plot.plot(
                combined_x,
                combined_y,
                pen=pg.mkPen((200, 50, 50), width=SECONDARY_LINE_WIDTH),
                name="Combined PnL",
            )

        product_final = product_pnl[-1] if product_pnl else 0.0
        combined_final = combined_y[-1] if combined_y else 0.0
        self.pnl_status_label.setText(
            f"{product} final PnL: {product_final:.2f}. Combined final PnL: {combined_final:.2f} "
            f"({source_text})."
        )

    def build_drawdown_path(self, values: List[float]) -> tuple[List[float], List[int]]:
        drawdowns: List[float] = []
        underwater: List[int] = []
        peak = values[0] if values else 0.0
        current_underwater = 0
        for value in values:
            if value >= peak:
                peak = value
                current_underwater = 0
            else:
                current_underwater += 1
            drawdowns.append(peak - value)
            underwater.append(current_underwater)
        return drawdowns, underwater

    def render_risk_tab(self, product: str, rows: List[PriceRow]) -> None:
        self.drawdown_plot.clear()
        self.underwater_plot.clear()
        self.ensure_legend(self.drawdown_plot)
        self.ensure_legend(self.underwater_plot)
        self.drawdown_plot.setTitle(f"{product} Drawdown")
        self.underwater_plot.setTitle(f"{product} Time Below Prior PnL High")

        if not rows:
            self.risk_status_label.setText("No PnL data available for risk analysis.")
            return

        x = [row.global_ts for row in rows]
        pnl = [row.pnl for row in rows]
        drawdowns, underwater = self.build_drawdown_path(pnl)
        self.drawdown_plot.plot(
            x,
            drawdowns,
            pen=pg.mkPen((210, 55, 55), width=MAIN_LINE_WIDTH),
            name="Drawdown",
        )
        self.drawdown_plot.addItem(
            pg.InfiniteLine(pos=0.0, angle=0, pen=pg.mkPen((90, 90, 90), width=REFERENCE_LINE_WIDTH, style=Qt.DashLine))
        )
        self.underwater_plot.plot(
            x,
            underwater,
            pen=pg.mkPen((90, 90, 200), width=MAIN_LINE_WIDTH),
            name="Underwater Samples",
        )

        max_dd = max(drawdowns) if drawdowns else 0.0
        trough_idx = drawdowns.index(max_dd) if drawdowns else 0
        longest_underwater = max(underwater) if underwater else 0
        underwater_pct = 100.0 * sum(1 for value in drawdowns if value > 1e-12) / len(drawdowns)
        self.risk_status_label.setText(
            f"Max drawdown: {max_dd:,.2f} at timestamp {x[trough_idx]:,}. "
            f"Longest drawdown stretch: {longest_underwater:,} samples. "
            f"Time below high: {underwater_pct:.1f}%."
        )

    def rolling_sum(self, values: List[float], window: int) -> List[float]:
        out: List[float] = []
        queue: List[float] = []
        running = 0.0
        for value in values:
            queue.append(value)
            running += value
            if len(queue) > window:
                running -= queue.pop(0)
            out.append(running)
        return out

    def rolling_sharpe(self, values: List[float], window: int) -> List[float]:
        out: List[float] = []
        queue: List[float] = []
        for value in values:
            queue.append(value)
            if len(queue) > window:
                queue.pop(0)
            if len(queue) < 2:
                out.append(0.0)
                continue
            mean_value = sum(queue) / len(queue)
            variance = sum((x - mean_value) ** 2 for x in queue) / (len(queue) - 1)
            if variance <= 1e-12:
                out.append(0.0)
            else:
                out.append(mean_value / math.sqrt(variance) * math.sqrt(len(queue)))
        return out

    def render_rolling_tab(self, product: str, rows: List[PriceRow]) -> None:
        self.period_return_plot.clear()
        self.rolling_sharpe_plot.clear()
        self.ensure_legend(self.period_return_plot)
        self.ensure_legend(self.rolling_sharpe_plot)
        window = self.rolling_window_spin.value()
        self.period_return_plot.setTitle(f"{product} Rolling {window}-Sample PnL")
        self.rolling_sharpe_plot.setTitle(f"{product} Rolling Sharpe")

        if len(rows) < 3:
            self.rolling_status_label.setText("Not enough PnL observations for rolling analysis.")
            return

        x = [row.global_ts for row in rows[1:]]
        changes = [rows[idx].pnl - rows[idx - 1].pnl for idx in range(1, len(rows))]
        period_returns = self.rolling_sum(changes, window)
        rolling_sharpe = self.rolling_sharpe(changes, window)

        self.period_return_plot.plot(
            x,
            period_returns,
            pen=pg.mkPen((0, 120, 190), width=MAIN_LINE_WIDTH),
            name="Rolling Period PnL",
        )
        self.period_return_plot.addItem(
            pg.InfiniteLine(pos=0.0, angle=0, pen=pg.mkPen((90, 90, 90), width=REFERENCE_LINE_WIDTH, style=Qt.DashLine))
        )
        self.rolling_sharpe_plot.plot(
            x,
            rolling_sharpe,
            pen=pg.mkPen((140, 75, 190), width=MAIN_LINE_WIDTH),
            name="Rolling Sharpe",
        )
        self.rolling_sharpe_plot.addItem(
            pg.InfiniteLine(pos=0.0, angle=0, pen=pg.mkPen((90, 90, 90), width=REFERENCE_LINE_WIDTH, style=Qt.DashLine))
        )

        negative_periods = sum(1 for value in period_returns if value < 0)
        worst_period = min(period_returns) if period_returns else 0.0
        best_period = max(period_returns) if period_returns else 0.0
        avg_rolling_sharpe = sum(rolling_sharpe) / len(rolling_sharpe) if rolling_sharpe else 0.0
        self.rolling_status_label.setText(
            f"Window: {window} samples. Negative rolling periods: {negative_periods:,}/{len(period_returns):,}. "
            f"Best period: {best_period:,.2f}. Worst period: {worst_period:,.2f}. "
            f"Average rolling Sharpe: {avg_rolling_sharpe:.3f}."
        )

    def fill_edge_details(self, product: str, rows: List[PriceRow]) -> List[dict]:
        fills = sorted(self.own_fills_by_product.get(product, []), key=lambda fill: fill.global_ts)
        if not fills or not rows:
            return []

        details: List[dict] = []
        inventory = 0
        current_day = None
        reference_rows = self.strategy_price_rows.get(product, rows) or rows
        for fill in fills:
            fill_day = fill.global_ts // DAY_TIMESTAMP_STRIDE
            if fill_day != current_day:
                inventory = 0
                current_day = fill_day
            row = self.find_row_at_ts(reference_rows, fill.global_ts)
            fair = row.wall_mid if row.wall_mid is not None else row.mid_price
            edge = fair - fill.price if fill.side == "BUY" else fill.price - fair
            edge_qty = edge * fill.quantity
            inventory += fill.quantity if fill.side == "BUY" else -fill.quantity
            details.append(
                {
                    "timestamp": fill.global_ts,
                    "side": fill.side,
                    "quantity": fill.quantity,
                    "price": fill.price,
                    "fair": fair,
                    "edge": edge,
                    "edge_qty": edge_qty,
                    "inventory": inventory,
                }
            )
        return details

    def render_execution_tab(self, product: str, rows: List[PriceRow]) -> None:
        self.fill_edge_plot.clear()
        self.cumulative_edge_plot.clear()
        self.ensure_legend(self.fill_edge_plot)
        self.ensure_legend(self.cumulative_edge_plot)
        self.fill_edge_plot.setTitle(f"{product} Fill Edge")
        self.cumulative_edge_plot.setTitle(f"{product} Cumulative Fill Edge")

        details = self.fill_edge_details(product, rows)
        if not details:
            self.execution_status_label.setText("No own fills available for execution analysis.")
            return

        buy = [item for item in details if item["side"] == "BUY"]
        sell = [item for item in details if item["side"] == "SELL"]
        if buy:
            self.fill_edge_plot.addItem(
                pg.ScatterPlotItem(
                    x=[item["timestamp"] for item in buy],
                    y=[item["edge"] for item in buy],
                    size=9,
                    symbol="t1",
                    brush=pg.mkBrush(30, 180, 60, 220),
                    pen=pg.mkPen(20, 120, 40, width=1.2),
                    name="Buy Edge",
                )
            )
        if sell:
            self.fill_edge_plot.addItem(
                pg.ScatterPlotItem(
                    x=[item["timestamp"] for item in sell],
                    y=[item["edge"] for item in sell],
                    size=9,
                    symbol="t",
                    brush=pg.mkBrush(190, 40, 40, 220),
                    pen=pg.mkPen(130, 20, 20, width=1.2),
                    name="Sell Edge",
                )
            )
        self.fill_edge_plot.addItem(
            pg.InfiniteLine(pos=0.0, angle=0, pen=pg.mkPen((90, 90, 90), width=REFERENCE_LINE_WIDTH, style=Qt.DashLine))
        )

        cumulative = []
        running = 0.0
        for item in details:
            running += item["edge_qty"]
            cumulative.append(running)
        self.cumulative_edge_plot.plot(
            [item["timestamp"] for item in details],
            cumulative,
            pen=pg.mkPen((0, 110, 200), width=MAIN_LINE_WIDTH),
            name="Cumulative Edge x Qty",
        )
        self.cumulative_edge_plot.addItem(
            pg.InfiniteLine(pos=0.0, angle=0, pen=pg.mkPen((90, 90, 90), width=REFERENCE_LINE_WIDTH, style=Qt.DashLine))
        )

        gross_volume = sum(item["quantity"] for item in details)
        weighted_edge = sum(item["edge_qty"] for item in details) / gross_volume if gross_volume else 0.0
        positive_edge = sum(1 for item in details if item["edge"] > 0)
        self.execution_status_label.setText(
            f"Fills: {len(details):,}. Gross volume: {gross_volume:,}. "
            f"Quantity-weighted edge: {weighted_edge:.3f}. "
            f"Positive-edge fills: {positive_edge:,}/{len(details):,}. "
            f"Cumulative edge x qty: {cumulative[-1]:,.2f}."
        )

    def set_table_item(self, row: int, column: int, value, decimals: Optional[int] = None) -> None:
        item = QTableWidgetItem()
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            text = f"{value:,.{decimals}f}" if decimals is not None else f"{value:,}"
            item.setData(Qt.DisplayRole, text)
            item.setData(Qt.UserRole, float(value))
        else:
            item.setText(str(value))
        self.trades_table.setItem(row, column, item)

    def render_trades_tab(self, product: str, rows: List[PriceRow]) -> None:
        details = self.fill_edge_details(product, rows)
        self.trades_table.setSortingEnabled(False)
        self.trades_table.setRowCount(len(details))

        for row_idx, item in enumerate(details):
            self.set_table_item(row_idx, 0, item["timestamp"])
            self.set_table_item(row_idx, 1, item["side"])
            self.set_table_item(row_idx, 2, item["quantity"])
            self.set_table_item(row_idx, 3, item["price"], 2)
            self.set_table_item(row_idx, 4, item["fair"], 2)
            self.set_table_item(row_idx, 5, item["edge"], 3)
            self.set_table_item(row_idx, 6, item["edge_qty"], 2)
            self.set_table_item(row_idx, 7, item["inventory"])

        self.trades_table.resizeColumnsToContents()
        self.trades_table.setSortingEnabled(True)
        if details:
            self.trades_status_label.setText(f"{len(details):,} own fills loaded for {product}. Click column headers to sort.")
        else:
            self.trades_status_label.setText(f"No own fills loaded for {product}.")

    def clamp(self, value: float, low: float, high: float) -> float:
        return max(low, min(high, value))

    def position_limit_for_product(self, product: str) -> Optional[int]:
        if product in POSITION_LIMITS:
            return POSITION_LIMITS[product]
        if product.startswith("VEV_"):
            return 300
        return None

    def sample_std(self, values: List[float]) -> Optional[float]:
        if len(values) < 2:
            return None
        mean_value = sum(values) / len(values)
        variance = sum((value - mean_value) ** 2 for value in values) / (len(values) - 1)
        return math.sqrt(variance)

    def max_drawdown(self, values: List[float]) -> tuple[float, float]:
        if not values:
            return 0.0, 0.0
        peak = values[0]
        best_peak = peak
        max_dd = 0.0
        for value in values:
            if value > peak:
                peak = value
            drawdown = peak - value
            if drawdown > max_dd:
                max_dd = drawdown
                best_peak = peak
        return max_dd, best_peak

    def drawdown_details(self, values: List[float]) -> dict:
        if not values:
            return {
                "max_dd": 0.0,
                "drawdown_peak": 0.0,
                "drawdown_trough": 0.0,
                "underwater_pct": 0.0,
                "longest_underwater": 0,
            }

        peak = values[0]
        max_dd = 0.0
        drawdown_peak = peak
        drawdown_trough = values[0]
        underwater_count = 0
        current_underwater = 0
        longest_underwater = 0

        for value in values:
            if value >= peak:
                peak = value
                current_underwater = 0
            else:
                underwater_count += 1
                current_underwater += 1
                longest_underwater = max(longest_underwater, current_underwater)

            drawdown = peak - value
            if drawdown > max_dd:
                max_dd = drawdown
                drawdown_peak = peak
                drawdown_trough = value

        return {
            "max_dd": max_dd,
            "drawdown_peak": drawdown_peak,
            "drawdown_trough": drawdown_trough,
            "underwater_pct": 100.0 * underwater_count / len(values),
            "longest_underwater": longest_underwater,
        }

    def skewness(self, values: List[float]) -> Optional[float]:
        if len(values) < 3:
            return None
        mean_value = sum(values) / len(values)
        variance = sum((value - mean_value) ** 2 for value in values) / len(values)
        if variance <= 1e-12:
            return 0.0
        sigma = math.sqrt(variance)
        return sum((value - mean_value) ** 3 for value in values) / len(values) / (sigma ** 3)

    def calculate_run_score(self, stats: dict) -> float:
        score = 50.0

        sharpe = stats.get("sharpe") or 0.0
        sortino = stats.get("sortino") or 0.0
        calmar = stats.get("calmar") or 0.0
        profit_factor = stats.get("profit_factor")
        win_rate = stats.get("win_rate")
        total_pnl = stats.get("total_pnl") or 0.0
        max_dd = stats.get("max_dd") or 0.0
        underwater_pct = stats.get("underwater_pct") or 0.0

        score += 18.0 * math.tanh(sharpe / 2.0)
        score += 14.0 * math.tanh(sortino / 3.0)
        score += 16.0 * math.tanh(calmar / 3.0)

        if profit_factor is not None:
            if math.isfinite(profit_factor) and profit_factor > 0:
                score += 10.0 * math.tanh(math.log(profit_factor))
            elif profit_factor == 0:
                score -= 10.0

        if win_rate is not None:
            score += 8.0 * self.clamp((win_rate - 50.0) / 50.0, -1.0, 1.0)

        if max_dd > 1e-12:
            drawdown_ratio = max_dd / max(abs(total_pnl), 1.0)
            score -= 14.0 * math.tanh(drawdown_ratio)

        score -= 6.0 * self.clamp(underwater_pct / 100.0, 0.0, 1.0)

        if total_pnl < 0:
            score -= 20.0 * math.tanh(abs(total_pnl) / max(max_dd, 1.0))

        return self.clamp(score, 0.0, 100.0)

    def calculate_pnl_stats(self, pnl_values: List[float]) -> dict:
        finite_values = [value for value in pnl_values if math.isfinite(value)]
        if not finite_values:
            return {}

        changes = [
            finite_values[idx] - finite_values[idx - 1]
            for idx in range(1, len(finite_values))
            if math.isfinite(finite_values[idx] - finite_values[idx - 1])
        ]
        nonzero_changes = [change for change in changes if abs(change) > 1e-12]
        risk_periods = len(self.strategy_graph_points) if self.strategy_graph_points else len(changes)
        risk_scale = math.sqrt(max(1, min(len(changes), risk_periods))) if changes else 1.0

        mean_change = sum(changes) / len(changes) if changes else 0.0
        change_std = self.sample_std(changes)
        downside_changes = [change for change in changes if change < 0]
        downside_std = self.sample_std(downside_changes)

        sharpe = None
        if change_std is not None and change_std > 1e-12:
            sharpe = mean_change / change_std * risk_scale

        sortino = None
        if downside_std is not None and downside_std > 1e-12:
            sortino = mean_change / downside_std * risk_scale

        drawdown = self.drawdown_details(finite_values)
        max_dd = drawdown["max_dd"]
        drawdown_peak = drawdown["drawdown_peak"]
        calmar = None
        if max_dd > 1e-12:
            calmar = finite_values[-1] / max_dd
        elif abs(finite_values[-1]) <= 1e-12:
            calmar = 0.0

        max_dd_pct = None
        if drawdown_peak > 1e-12:
            max_dd_pct = max_dd / drawdown_peak * 100.0
        elif max_dd <= 1e-12:
            max_dd_pct = 0.0

        win_rate = None
        if nonzero_changes:
            win_rate = 100.0 * sum(1 for change in nonzero_changes if change > 0) / len(nonzero_changes)

        cvar_95 = None
        if changes:
            tail_count = max(1, math.ceil(0.05 * len(changes)))
            cvar_95 = sum(sorted(changes)[:tail_count]) / tail_count

        gross_profit = sum(change for change in changes if change > 0)
        gross_loss = -sum(change for change in changes if change < 0)
        profit_factor = None
        if gross_loss > 1e-12:
            profit_factor = gross_profit / gross_loss
        elif gross_profit > 1e-12:
            profit_factor = math.inf

        expectancy = None
        if nonzero_changes:
            expectancy = sum(nonzero_changes) / len(nonzero_changes)

        best_step = max(changes) if changes else None
        worst_step = min(changes) if changes else None

        stats = {
            "total_pnl": finite_values[-1],
            "sharpe": sharpe,
            "sortino": sortino,
            "calmar": calmar,
            "win_rate": win_rate,
            "max_dd": max_dd,
            "max_dd_pct": max_dd_pct,
            "underwater_pct": drawdown["underwater_pct"],
            "longest_underwater": drawdown["longest_underwater"],
            "drawdown_trough": drawdown["drawdown_trough"],
            "cvar_95": cvar_95,
            "profit_factor": profit_factor,
            "expectancy": expectancy,
            "best_step": best_step,
            "worst_step": worst_step,
            "skewness": self.skewness(changes),
            "data_points": len(finite_values),
            "change_points": len(changes),
            "risk_periods": risk_periods,
        }
        stats["score"] = self.calculate_run_score(stats)
        return stats

    def format_optional_float(self, value, decimals: int = 2, suffix: str = "") -> str:
        if value is None:
            return "N/A"
        try:
            numeric = float(value)
        except Exception:
            return "N/A"
        if math.isinf(numeric):
            return f"Inf{suffix}"
        if not math.isfinite(numeric):
            return "N/A"
        return f"{numeric:,.{decimals}f}{suffix}"

    def populate_stats_labels(self, labels: Dict[str, QLabel], stats: dict, execution_stats: dict) -> None:
        labels["score"].setText(self.format_optional_float(stats["score"], 1))
        labels["total_pnl"].setText(self.format_optional_float(stats["total_pnl"], 0))
        labels["sharpe"].setText(self.format_optional_float(stats["sharpe"], 3))
        labels["sortino"].setText(self.format_optional_float(stats["sortino"], 3))
        labels["calmar"].setText(self.format_optional_float(stats["calmar"], 3))
        labels["win_rate"].setText(self.format_optional_float(stats["win_rate"], 1, "%"))
        labels["max_dd"].setText(self.format_optional_float(stats["max_dd_pct"], 2, "%"))
        labels["max_dd_abs"].setText(self.format_optional_float(stats["max_dd"], 2))
        labels["underwater_pct"].setText(self.format_optional_float(stats["underwater_pct"], 1, "%"))
        labels["cvar_95"].setText(self.format_optional_float(stats["cvar_95"], 2))
        labels["profit_factor"].setText(self.format_optional_float(stats["profit_factor"], 3))
        labels["expectancy"].setText(self.format_optional_float(stats["expectancy"], 2))
        labels["best_step"].setText(self.format_optional_float(stats["best_step"], 2))
        labels["worst_step"].setText(self.format_optional_float(stats["worst_step"], 2))
        labels["skewness"].setText(self.format_optional_float(stats["skewness"], 3))
        labels["data_points"].setText(f"{stats['data_points']:,}")
        labels["fill_count"].setText(f"{execution_stats['fill_count']:,}")
        labels["gross_volume"].setText(f"{execution_stats['gross_volume']:,}")
        labels["avg_fill_edge"].setText(self.format_optional_float(execution_stats["avg_fill_edge"], 3))
        labels["quote_count"].setText(f"{execution_stats['quote_count']:,}")
        labels["quote_fill_rate"].setText(self.format_optional_float(execution_stats["quote_fill_rate"], 1, "%"))
        labels["max_inventory"].setText(f"{execution_stats['max_inventory']:,}")
        labels["inv_utilization"].setText(self.format_optional_float(execution_stats["inv_utilization"], 1, "%"))

    def calculate_execution_stats(self, product: str, rows: List[PriceRow]) -> dict:
        fills = self.own_fills_by_product.get(product, [])
        quotes = self.own_quotes_by_product.get(product, [])

        gross_volume = sum(fill.quantity for fill in fills)
        buy_volume = sum(fill.quantity for fill in fills if fill.side == "BUY")
        sell_volume = sum(fill.quantity for fill in fills if fill.side == "SELL")
        quote_count = len(quotes)
        fill_count = len(fills)
        quote_fill_rate = None
        if quote_count > 0:
            quote_fill_rate = 100.0 * fill_count / quote_count

        avg_fill_edge = None
        total_fill_edge = None
        if fills and rows and gross_volume > 0:
            edge_sum = 0.0
            reference_rows = self.strategy_price_rows.get(product, rows) or rows
            for fill in fills:
                row = self.find_row_at_ts(reference_rows, fill.global_ts)
                fair = row.wall_mid if row.wall_mid is not None else row.mid_price
                edge = fair - fill.price if fill.side == "BUY" else fill.price - fair
                edge_sum += edge * fill.quantity
            avg_fill_edge = edge_sum / gross_volume
            total_fill_edge = edge_sum

        _, inventory_vals = self.build_inventory_path(rows, fills) if rows else ([], [])
        max_inventory = max((abs(value) for value in inventory_vals), default=0)
        final_inventory = inventory_vals[-1] if inventory_vals else 0
        final_position = self.strategy_final_positions.get(product)
        position_limit = self.position_limit_for_product(product)
        inv_utilization = None
        if position_limit:
            inv_utilization = 100.0 * max_inventory / position_limit

        return {
            "fill_count": fill_count,
            "gross_volume": gross_volume,
            "buy_volume": buy_volume,
            "sell_volume": sell_volume,
            "quote_count": quote_count,
            "quote_fill_rate": quote_fill_rate,
            "avg_fill_edge": avg_fill_edge,
            "total_fill_edge": total_fill_edge,
            "max_inventory": max_inventory,
            "final_inventory": final_inventory,
            "final_position": final_position,
            "position_limit": position_limit,
            "inv_utilization": inv_utilization,
        }

    def calculate_combined_execution_stats(self) -> dict:
        products = sorted(
            set(self.strategy_price_rows.keys())
            | set(self.dataset.price_rows.keys())
            | set(self.own_fills_by_product.keys())
            | set(self.own_quotes_by_product.keys())
        )
        fills_by_product = {
            product: self.own_fills_by_product.get(product, [])
            for product in products
        }
        all_fills = [
            fill
            for fills in fills_by_product.values()
            for fill in fills
        ]
        all_quotes = [
            quote
            for product in products
            for quote in self.own_quotes_by_product.get(product, [])
        ]

        gross_volume = sum(fill.quantity for fill in all_fills)
        quote_count = len(all_quotes)
        fill_count = len(all_fills)
        quote_fill_rate = None
        if quote_count > 0:
            quote_fill_rate = 100.0 * fill_count / quote_count

        edge_sum = 0.0
        edge_qty = 0
        for product, fills in fills_by_product.items():
            rows = self.strategy_price_rows.get(product) or self.dataset.price_rows.get(product) or []
            if not rows:
                continue
            for fill in fills:
                row = self.find_row_at_ts(rows, fill.global_ts)
                fair = row.wall_mid if row.wall_mid is not None else row.mid_price
                edge = fair - fill.price if fill.side == "BUY" else fill.price - fair
                edge_sum += edge * fill.quantity
                edge_qty += fill.quantity

        avg_fill_edge = edge_sum / edge_qty if edge_qty > 0 else None

        inventory_by_product: Dict[str, int] = defaultdict(int)
        max_gross_inventory = 0
        current_day = None
        for fill in sorted(all_fills, key=lambda item: item.global_ts):
            fill_day = fill.global_ts // DAY_TIMESTAMP_STRIDE
            if fill_day != current_day:
                inventory_by_product = defaultdict(int)
                current_day = fill_day
            inventory_by_product[fill.product] += fill.quantity if fill.side == "BUY" else -fill.quantity
            gross_inventory = sum(abs(value) for value in inventory_by_product.values())
            max_gross_inventory = max(max_gross_inventory, gross_inventory)

        known_limits = [
            limit
            for product in products
            for limit in [self.position_limit_for_product(product)]
            if limit is not None
        ]
        total_position_limit = sum(known_limits) if known_limits else None
        inv_utilization = None
        if total_position_limit:
            inv_utilization = 100.0 * max_gross_inventory / total_position_limit

        return {
            "fill_count": fill_count,
            "gross_volume": gross_volume,
            "buy_volume": sum(fill.quantity for fill in all_fills if fill.side == "BUY"),
            "sell_volume": sum(fill.quantity for fill in all_fills if fill.side == "SELL"),
            "quote_count": quote_count,
            "quote_fill_rate": quote_fill_rate,
            "avg_fill_edge": avg_fill_edge,
            "total_fill_edge": edge_sum if edge_qty > 0 else None,
            "max_inventory": max_gross_inventory,
            "final_inventory": sum(abs(value) for value in inventory_by_product.values()),
            "final_position": None,
            "position_limit": total_position_limit,
            "inv_utilization": inv_utilization,
            "product_count": len(products),
        }

    def render_stats_tab(self, product: str, rows: List[PriceRow]) -> None:
        if not hasattr(self, "stats_value_labels"):
            return

        pnl_values = [row.pnl for row in rows]
        stats = self.calculate_pnl_stats(pnl_values)
        if not stats:
            self.clear_stats_tab()
            return
        execution_stats = self.calculate_execution_stats(product, rows)
        self.populate_stats_labels(self.stats_value_labels, stats, execution_stats)

        source_text = self.strategy_source_label if self.strategy_log_path else "loaded price files"
        run_total = "Unknown" if self.strategy_run_profit is None else f"{self.strategy_run_profit:,.2f}"
        limit_text = "Unknown" if execution_stats["position_limit"] is None else str(execution_stats["position_limit"])
        avg_edge_text = self.format_optional_float(execution_stats["avg_fill_edge"], 3)
        self.stats_status_label.setText(
            f"Stats for {product} PnL from {source_text}. "
            f"Score: {stats['score']:.1f}/100. "
            f"Absolute max drawdown: {stats['max_dd']:,.2f}. "
            f"Longest drawdown: {stats['longest_underwater']:,} samples. "
            f"Max inventory: {execution_stats['max_inventory']:,}/{limit_text}. "
            f"Avg fill edge: {avg_edge_text}. "
            f"Risk scale periods: {stats['risk_periods']:,}. Run total: {run_total}. "
            f"Score formula blends Sharpe, Sortino, Calmar, profit factor, win rate, drawdown size, and time underwater."
        )

    def render_combined_stats_tab(self) -> None:
        if not hasattr(self, "combined_stats_value_labels"):
            return

        combined_x, combined_y, source = self.combined_pnl_series_for_stats()
        stats = self.calculate_pnl_stats(combined_y)
        if not stats:
            self.clear_combined_stats_tab()
            return

        execution_stats = self.calculate_combined_execution_stats()
        self.populate_stats_labels(self.combined_stats_value_labels, stats, execution_stats)

        run_total = "Unknown" if self.strategy_run_profit is None else f"{self.strategy_run_profit:,.2f}"
        limit_text = "Unknown" if execution_stats["position_limit"] is None else str(execution_stats["position_limit"])
        avg_edge_text = self.format_optional_float(execution_stats["avg_fill_edge"], 3)
        self.combined_stats_status_label.setText(
            f"Combined stats from {self.strategy_source_label if self.strategy_log_path else source}. "
            f"Score: {stats['score']:.1f}/100. "
            f"Total PnL: {stats['total_pnl']:,.2f}. "
            f"Absolute max drawdown: {stats['max_dd']:,.2f}. "
            f"Longest drawdown: {stats['longest_underwater']:,} samples. "
            f"Products: {execution_stats['product_count']:,}. "
            f"Max gross inventory: {execution_stats['max_inventory']:,}/{limit_text}. "
            f"Avg fill edge: {avg_edge_text}. "
            f"Risk scale periods: {stats['risk_periods']:,}. Run total: {run_total}."
        )

    def infer_tick_step(self, rows: List[PriceRow]) -> int:
        deltas: List[float] = []
        for idx in range(1, min(len(rows), 25)):
            delta = (rows[idx].global_ts - rows[idx - 1].global_ts) / 100.0
            if delta > 0:
                deltas.append(delta)
        if not deltas:
            return 1
        return max(1, int(round(min(deltas))))

    def linear_regression(self, xs: List[float], ys: List[float]) -> tuple[float, float]:
        if len(xs) != len(ys) or len(xs) < 2:
            return 0.0, ys[-1] if ys else 0.0
        mean_x = sum(xs) / len(xs)
        mean_y = sum(ys) / len(ys)
        denom = sum((x - mean_x) ** 2 for x in xs)
        if denom <= 1e-12:
            return 0.0, mean_y
        slope = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys)) / denom
        intercept = mean_y - slope * mean_x
        return slope, intercept

    def render_spread_analysis_tab(self, product: str, rows: List[PriceRow]) -> None:
        self.spread_analysis_plot.clear()
        self.spread_residual_plot.clear()
        self.ensure_legend(self.spread_analysis_plot)
        self.ensure_legend(self.spread_residual_plot)
        self.spread_analysis_plot.setTitle(f"{product} Spread Analysis")
        self.spread_residual_plot.setTitle(f"{product} Residual / Z-Score")

        x = [row.global_ts for row in rows]
        spread = [
            (row.best_ask - row.best_bid) if row.best_ask is not None and row.best_bid is not None else math.nan
            for row in rows
        ]
        residual = [row.mid_price - (row.wall_mid if row.wall_mid is not None else row.mid_price) for row in rows]
        residual_mean = self.rolling_mean(residual, 50)
        residual_std = self.rolling_std(residual, 50)
        zscore = [0.0 if std <= 1e-9 else (value - mean_value) / std for value, mean_value, std in zip(residual, residual_mean, residual_std)]

        self.spread_analysis_plot.plot(x, spread, pen=pg.mkPen((80, 80, 80), width=SECONDARY_LINE_WIDTH), name="Top Spread")
        self.spread_analysis_plot.plot(x, residual_mean, pen=pg.mkPen((0, 140, 200), width=SECONDARY_LINE_WIDTH), name="Residual Mean")
        self.spread_residual_plot.plot(x, residual, pen=pg.mkPen((255, 140, 0), width=SECONDARY_LINE_WIDTH), name="Mid-Wall")
        self.spread_residual_plot.plot(x, zscore, pen=pg.mkPen((130, 50, 220), width=SECONDARY_LINE_WIDTH), name="Residual Z")

    def render_smile_tab(self) -> None:
        self.smile_plot.clear()
        self.ensure_legend(self.smile_plot)
        self.smile_plot.setTitle("Cross-Strike Price / Smile Proxy")
        option_like = []
        pattern = re.compile(r"(\d{4,5})")
        for product, rows in self.dataset.price_rows.items():
            match = pattern.search(product)
            if not match or not rows:
                continue
            option_like.append((float(match.group(1)), rows[-1].mid_price, product))

        if len(option_like) < 3:
            self.smile_status_label.setText(
                "No option-like cross-strike dataset detected yet. "
                "This tab is ready for later rounds when product names include strikes."
            )
            return

        option_like.sort(key=lambda item: item[0])
        xs = [item[0] for item in option_like]
        ys = [item[1] for item in option_like]
        self.smile_plot.plot(xs, ys, pen=pg.mkPen((0, 0, 0), width=MAIN_LINE_WIDTH), symbol="o", symbolBrush=(255, 80, 80))
        self.smile_status_label.setText(
            "Showing a first-pass cross-strike smile proxy using latest mids. "
            "We can replace this with proper IV fitting when option data arrives."
        )

    def autocorr(self, values: List[float], lag: int) -> float:
        if lag <= 0 or len(values) <= lag:
            return math.nan
        xs = values[:-lag]
        ys = values[lag:]
        mean_x = sum(xs) / len(xs)
        mean_y = sum(ys) / len(ys)
        denom_x = sum((x - mean_x) ** 2 for x in xs)
        denom_y = sum((y - mean_y) ** 2 for y in ys)
        if denom_x <= 1e-12 or denom_y <= 1e-12:
            return math.nan
        numer = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
        return numer / math.sqrt(denom_x * denom_y)

    def render_autocorr_tab(self, product: str, rows: List[PriceRow]) -> None:
        self.autocorr_plot.clear()
        self.ensure_legend(self.autocorr_plot)
        self.autocorr_plot.setTitle(f"{product} Return Autocorrelation")
        mids = [row.mid_price for row in rows]
        returns = [mids[i] - mids[i - 1] for i in range(1, len(mids))]
        lags = list(range(1, min(40, len(returns))))
        values = [self.autocorr(returns, lag) for lag in lags]
        self.autocorr_plot.plot(lags, values, pen=pg.mkPen((200, 30, 30), width=MAIN_LINE_WIDTH), symbol="o", symbolSize=6)
        self.autocorr_status_label.setText(
            "Lag autocorrelation of mid returns for the selected product. "
            "Useful for spotting short-horizon mean reversion or persistence."
        )

    def bucket_histogram(self, values: List[float], bucket_size: float) -> tuple[List[float], List[int]]:
        if not values or bucket_size <= 0:
            return [], []
        counts = defaultdict(int)
        for value in values:
            bucket = round(value / bucket_size) * bucket_size
            counts[bucket] += 1
        buckets = sorted(counts.keys())
        return buckets, [counts[b] for b in buckets]

    def plot_histogram_series(
        self,
        plot: pg.PlotWidget,
        buckets: List[float],
        counts: List[int],
        name: str,
        pen_color,
        brush_color,
    ):
        if not buckets:
            return None
        return plot.plot(
            buckets,
            counts,
            fillLevel=0,
            brush=brush_color,
            pen=pg.mkPen(pen_color, width=SECONDARY_LINE_WIDTH),
            name=name,
        )

    def render_pepper_tab(self) -> None:
        self.pepper_drift_plot.clear()
        self.pepper_distance_plot.clear()
        self.pepper_inventory_plot.clear()
        self.pepper_drift_hist_plot.clear()
        self.pepper_distance_hist_plot.clear()
        self.ensure_legend(self.pepper_drift_plot)
        self.ensure_legend(self.pepper_distance_plot)
        self.ensure_legend(self.pepper_inventory_plot)
        self.ensure_legend(self.pepper_drift_hist_plot)
        self.ensure_legend(self.pepper_distance_hist_plot)
        self.pepper_drift_plot.setTitle("Pepper Root Rolling Drift by Window")
        self.pepper_distance_plot.setTitle("Pepper Root Residual / Executable Edge")
        self.pepper_inventory_plot.setTitle("Pepper Root Inventory / Opportunity")
        self.pepper_drift_hist_plot.setTitle("Pepper Root Drift Distribution")
        self.pepper_distance_hist_plot.setTitle("Pepper Root Distance Distribution")

        pepper_rows = self.strategy_price_rows.get("INTARIAN_PEPPER_ROOT") or self.dataset.price_rows.get("INTARIAN_PEPPER_ROOT", [])
        if len(pepper_rows) < 5:
            self.pepper_status_label.setText("Load pepper data to see drift diagnostics.")
            return

        tick_step = self.infer_tick_step(pepper_rows)
        available_ticks = len(pepper_rows) * tick_step
        window = self.pepper_window_spin.value()
        if available_ticks < window:
            self.pepper_status_label.setText(
                f"Pepper has about {available_ticks} raw ticks loaded. Increase data or reduce the drift window below {available_ticks}."
            )
            return

        ticks = [row.global_ts / 100.0 for row in pepper_rows]
        mids = [row.mid_price for row in pepper_rows]
        comparison_windows: List[int] = []
        for candidate in [20, 50, 100, 200]:
            if candidate <= available_ticks:
                comparison_windows.append(candidate)
        if window not in comparison_windows:
            comparison_windows.append(window)
        comparison_windows = sorted(set(comparison_windows))

        comparison_colors = {
            comparison_windows[idx]: color
            for idx, color in enumerate(
                [
                    (0, 120, 220),
                    (255, 140, 0),
                    (140, 40, 200),
                    (30, 160, 90),
                    (190, 40, 60),
                ][: len(comparison_windows)]
            )
        }

        selected_slopes: List[float] = []
        residual_x: List[int] = []
        residual_y: List[float] = []
        fair_by_ts: Dict[int, float] = {}
        buy_edge_by_ts: Dict[int, float] = {}
        sell_edge_by_ts: Dict[int, float] = {}

        for compare_window in comparison_windows:
            row_window = max(2, int(math.ceil(compare_window / tick_step)))
            x_vals: List[int] = []
            slopes: List[float] = []
            for idx in range(row_window - 1, len(pepper_rows)):
                window_ticks = ticks[idx - row_window + 1 : idx + 1]
                window_mids = mids[idx - row_window + 1 : idx + 1]
                slope, intercept = self.linear_regression(window_ticks, window_mids)
                x_vals.append(pepper_rows[idx].global_ts)
                slopes.append(slope)

                if compare_window == window:
                    estimated = intercept + slope * ticks[idx]
                    fair_by_ts[pepper_rows[idx].global_ts] = estimated
                    residual_x.append(pepper_rows[idx].global_ts)
                    residual_y.append(pepper_rows[idx].mid_price - estimated)
                    selected_slopes.append(slope)
                    buy_edge_by_ts[pepper_rows[idx].global_ts] = (
                        estimated - pepper_rows[idx].best_ask if pepper_rows[idx].best_ask is not None else math.nan
                    )
                    sell_edge_by_ts[pepper_rows[idx].global_ts] = (
                        pepper_rows[idx].best_bid - estimated if pepper_rows[idx].best_bid is not None else math.nan
                    )

            self.pepper_drift_plot.plot(
                x_vals,
                slopes,
                pen=pg.mkPen(comparison_colors[compare_window], width=SECONDARY_LINE_WIDTH),
                name=f"Window {compare_window}",
            )

        self.pepper_drift_plot.addItem(
            pg.InfiniteLine(pos=0.1, angle=0, pen=pg.mkPen((255, 140, 0), width=REFERENCE_LINE_WIDTH, style=Qt.DashLine))
        )
        self.pepper_drift_plot.plot(
            [],
            [],
            pen=pg.mkPen((255, 140, 0), width=REFERENCE_LINE_WIDTH, style=Qt.DashLine),
            name="Baseline 0.1",
        )

        buy_edge_series = [buy_edge_by_ts.get(ts, math.nan) for ts in residual_x]
        sell_edge_series = [sell_edge_by_ts.get(ts, math.nan) for ts in residual_x]

        self.pepper_distance_plot.plot(
            residual_x,
            residual_y,
            pen=pg.mkPen((140, 40, 200), width=SECONDARY_LINE_WIDTH),
            symbol="o",
            symbolSize=4,
            symbolBrush=(140, 40, 200, 120),
            name="Residual",
        )
        self.pepper_distance_plot.plot(
            residual_x,
            buy_edge_series,
            pen=pg.mkPen((30, 160, 90), width=SECONDARY_LINE_WIDTH),
            name="Fair - Best Ask",
        )
        self.pepper_distance_plot.plot(
            residual_x,
            sell_edge_series,
            pen=pg.mkPen((200, 60, 60), width=SECONDARY_LINE_WIDTH),
            name="Best Bid - Fair",
        )
        self.pepper_distance_plot.addItem(
            pg.InfiniteLine(pos=0.0, angle=0, pen=pg.mkPen((80, 80, 80), width=REFERENCE_LINE_WIDTH, style=Qt.DashLine))
        )
        self.pepper_distance_plot.plot(
            [],
            [],
            pen=pg.mkPen((80, 80, 80), width=REFERENCE_LINE_WIDTH, style=Qt.DashLine),
            name="Zero Line",
        )

        own_fills = self.own_fills_by_product.get("INTARIAN_PEPPER_ROOT", [])
        inventory_x, inventory_series = self.build_inventory_path(pepper_rows, own_fills)
        self.pepper_inventory_plot.plot(
            inventory_x,
            inventory_series,
            pen=pg.mkPen((0, 110, 220), width=3.2),
            name="Inventory",
        )
        self.pepper_inventory_plot.setYRange(-5.0, 85.0, padding=0.01)
        self.pepper_inventory_plot.addItem(
            pg.InfiniteLine(pos=0.0, angle=0, pen=pg.mkPen((80, 80, 80), width=REFERENCE_LINE_WIDTH, style=Qt.DashLine))
        )
        self.pepper_inventory_plot.plot(
            [],
            [],
            pen=pg.mkPen((80, 80, 80), width=REFERENCE_LINE_WIDTH, style=Qt.DashLine),
            name="Flat 0",
        )

        if own_fills:
            buy_fill_x, buy_fill_y, sell_fill_x, sell_fill_y = [], [], [], []
            buy_inv_x, buy_inv_y, sell_inv_x, sell_inv_y = [], [], [], []
            running_inventory = 0
            for fill in own_fills:
                fair_value = fair_by_ts.get(fill.global_ts)
                if fill.side == "BUY":
                    running_inventory += fill.quantity
                    buy_inv_x.append(fill.global_ts)
                    buy_inv_y.append(running_inventory)
                    if fair_value is not None:
                        buy_fill_x.append(fill.global_ts)
                        buy_fill_y.append(fair_value - fill.price)
                else:
                    running_inventory -= fill.quantity
                    sell_inv_x.append(fill.global_ts)
                    sell_inv_y.append(running_inventory)
                    if fair_value is not None:
                        sell_fill_x.append(fill.global_ts)
                        sell_fill_y.append(fill.price - fair_value)

            if buy_fill_x:
                self.pepper_distance_plot.addItem(
                    pg.ScatterPlotItem(
                        x=buy_fill_x,
                        y=buy_fill_y,
                        size=10,
                        symbol="t1",
                        brush=pg.mkBrush(30, 180, 60, 220),
                        pen=pg.mkPen(20, 120, 40, width=1.3),
                        name="Own Buy Fills",
                    )
                )
                self.pepper_inventory_plot.addItem(
                    pg.ScatterPlotItem(
                        x=buy_inv_x,
                        y=buy_inv_y,
                        size=10,
                        symbol="t1",
                        brush=pg.mkBrush(30, 180, 60, 220),
                        pen=pg.mkPen(20, 120, 40, width=1.3),
                        name="Buy Fills",
                    )
                )
            if sell_fill_x:
                self.pepper_distance_plot.addItem(
                    pg.ScatterPlotItem(
                        x=sell_fill_x,
                        y=sell_fill_y,
                        size=10,
                        symbol="t",
                        brush=pg.mkBrush(190, 40, 40, 220),
                        pen=pg.mkPen(130, 20, 20, width=1.3),
                        name="Own Sell Fills",
                    )
                )
                self.pepper_inventory_plot.addItem(
                    pg.ScatterPlotItem(
                        x=sell_inv_x,
                        y=sell_inv_y,
                        size=10,
                        symbol="t",
                        brush=pg.mkBrush(190, 40, 40, 220),
                        pen=pg.mkPen(130, 20, 20, width=1.3),
                        name="Sell Fills",
                    )
                )

        drift_buckets, drift_counts = self.bucket_histogram(selected_slopes, 0.005)
        if drift_buckets:
            self.plot_histogram_series(
                self.pepper_drift_hist_plot,
                drift_buckets,
                drift_counts,
                "Slope Histogram",
                (0, 120, 220),
                (0, 120, 220, 120),
            )
            drift_baseline = pg.InfiniteLine(pos=0.1, angle=90, pen=pg.mkPen((255, 140, 0), width=REFERENCE_LINE_WIDTH, style=Qt.DashLine))
            self.pepper_drift_hist_plot.addItem(drift_baseline)
            self.add_legend_sample(
                self.pepper_drift_hist_plot,
                "Baseline 0.1",
                targets=[drift_baseline],
                pen=pg.mkPen((255, 140, 0), width=REFERENCE_LINE_WIDTH, style=Qt.DashLine),
            )

        distance_buckets, distance_counts = self.bucket_histogram(residual_y, 0.5)
        if distance_buckets:
            self.plot_histogram_series(
                self.pepper_distance_hist_plot,
                distance_buckets,
                distance_counts,
                "Distance Histogram",
                (255, 90, 90),
                (255, 90, 90, 110),
            )
            zero_distance_line = pg.InfiniteLine(pos=0.0, angle=90, pen=pg.mkPen((80, 80, 80), width=REFERENCE_LINE_WIDTH, style=Qt.DashLine))
            self.pepper_distance_hist_plot.addItem(zero_distance_line)
            self.add_legend_sample(
                self.pepper_distance_hist_plot,
                "Zero Distance",
                targets=[zero_distance_line],
                pen=pg.mkPen((80, 80, 80), width=REFERENCE_LINE_WIDTH, style=Qt.DashLine),
            )

        buy_edge_hist_values = [value for value in buy_edge_series if not math.isnan(value)]
        buy_edge_buckets, buy_edge_counts = self.bucket_histogram(buy_edge_hist_values, 0.5)
        if buy_edge_buckets:
            self.plot_histogram_series(
                self.pepper_distance_hist_plot,
                buy_edge_buckets,
                buy_edge_counts,
                "Fair - Best Ask Dist",
                (30, 160, 90),
                (30, 160, 90, 95),
            )

        sell_edge_hist_values = [value for value in sell_edge_series if not math.isnan(value)]
        sell_edge_buckets, sell_edge_counts = self.bucket_histogram(sell_edge_hist_values, 0.5)
        if sell_edge_buckets:
            self.plot_histogram_series(
                self.pepper_distance_hist_plot,
                sell_edge_buckets,
                sell_edge_counts,
                "Best Bid - Fair Dist",
                (200, 60, 60),
                (200, 60, 60, 95),
            )

        avg_slope = sum(selected_slopes) / len(selected_slopes)
        avg_abs_residual = sum(abs(v) for v in residual_y) / len(residual_y)
        min_slope = min(selected_slopes)
        max_slope = max(selected_slopes)
        large_edge = float(self.large_edge_spin.value())
        final_inventory = inventory_series[-1] if inventory_series else 0
        min_inventory = min(inventory_series) if inventory_series else 0
        max_inventory = max(inventory_series) if inventory_series else 0
        inventory_selected = inventory_series[window - 1 :]
        buy_room_count = sum(1 for residual, inv in zip(residual_y, inventory_selected) if residual <= -large_edge and inv < 80)
        sell_room_count = sum(1 for residual, inv in zip(residual_y, inventory_selected) if residual >= large_edge and inv > 0)
        exec_buy_room_count = sum(1 for edge, inv in zip(buy_edge_series, inventory_selected) if not math.isnan(edge) and edge >= large_edge and inv < 80)
        exec_sell_room_count = sum(1 for edge, inv in zip(sell_edge_series, inventory_selected) if not math.isnan(edge) and edge >= large_edge and inv > 0)
        fill_count = len(own_fills)
        first_fill_ts = own_fills[0].global_ts if own_fills else None
        last_fill_ts = own_fills[-1].global_ts if own_fills else None
        self.pepper_status_label.setText(
            "\n".join(
                [
                    f"Window: {window} ticks",
                    f"Average rolling slope: {avg_slope:.5f}",
                    f"Rolling slope range: [{min_slope:.5f}, {max_slope:.5f}]",
                    f"Expected baseline slope: 0.10000",
                    f"Average absolute distance from estimated fair: {avg_abs_residual:.4f}",
                    f"Residual samples: {len(residual_y)}",
                    f"Loaded own fills: {fill_count}" + (f" from {self.strategy_log_path.name}" if self.strategy_log_path else ""),
                    f"Inventory path: min {min_inventory}, max {max_inventory}, final {final_inventory}",
                    f"Fill timestamps: {first_fill_ts if first_fill_ts is not None else 'None'} -> {last_fill_ts if last_fill_ts is not None else 'None'}",
                    f"|Residual| >= {large_edge:.0f} with room: buy {buy_room_count}, sell {sell_room_count}",
                    f"Executable edge >= {large_edge:.0f} with room: buy {exec_buy_room_count}, sell {exec_sell_room_count}",
                    f"Comparison windows shown: {', '.join(str(w) for w in comparison_windows)}",
                ]
            )
        )

    def find_row_at_ts(self, rows: List[PriceRow], global_ts: int) -> PriceRow:
        if not rows:
            raise ValueError("No rows loaded")
        cache_key = (id(rows), len(rows), rows[0].global_ts, rows[-1].global_ts)
        timestamps = self._row_ts_cache.get(cache_key)
        if timestamps is None:
            timestamps = [row.global_ts for row in rows]
            self._row_ts_cache[cache_key] = timestamps

        idx = bisect_left(timestamps, global_ts)
        if idx <= 0:
            return rows[0]
        if idx >= len(rows):
            return rows[-1]

        before = rows[idx - 1]
        after = rows[idx]
        if abs(before.global_ts - global_ts) <= abs(after.global_ts - global_ts):
            return before
        return after

    def on_mouse_moved(self, position) -> None:
        if not self.current_price_rows:
            return
        vb = self.orderbook_plot.getPlotItem().vb
        point = vb.mapSceneToView(position)
        target_ts = int(round(point.x()))
        row = self.find_row_at_ts(self.current_price_rows, target_ts)

        relevant_trades = [t for t in self.current_trade_rows if t.global_ts == row.global_ts]
        trade_text = "No public trades"
        if relevant_trades:
            trade_text = ", ".join(f"{t.quantity}@{int(t.price)}" for t in relevant_trades[:6])
        own_fills = [f for f in self.own_fills_by_product.get(row.product, []) if f.global_ts == row.global_ts]
        own_fill_text = "No own fills"
        if own_fills:
            own_fill_text = ", ".join(f"{fill.side} {fill.quantity}@{int(fill.price)}" for fill in own_fills[:6])

        best_bid = "None" if row.best_bid is None else f"{row.best_bid:.1f}"
        best_ask = "None" if row.best_ask is None else f"{row.best_ask:.1f}"
        wall_mid = "None" if row.wall_mid is None else f"{row.wall_mid:.2f}"
        spread = "None"
        if row.best_bid is not None and row.best_ask is not None:
            spread = f"{row.best_ask - row.best_bid:.2f}"

        self.hover_label.setText(
            "\n".join(
                [
                    f"Product: {row.product}",
                    f"Day / Timestamp: {row.day} / {row.timestamp}",
                    f"Global Timestamp: {row.global_ts}",
                    f"Mid: {row.mid_price:.2f}",
                    f"Best Bid / Ask: {best_bid} / {best_ask}",
                    f"Wall Mid: {wall_mid}",
                    f"Spread: {spread}",
                    f"Trades: {trade_text}",
                    f"Own Fills: {own_fill_text}",
                ]
            )
        )

    def update_summary(self, product: str, rows: List[PriceRow]) -> None:
        unique_days = sorted({row.day for row in rows})
        trade_count = len(self.current_trade_rows)
        own_fill_count = len(self.own_fills_by_product.get(product, []))
        own_quote_count = len(self.own_quotes_by_product.get(product, []))
        avg_spread_values = [
            row.best_ask - row.best_bid
            for row in rows
            if row.best_ask is not None and row.best_bid is not None
        ]
        avg_spread = sum(avg_spread_values) / len(avg_spread_values) if avg_spread_values else 0.0
        if self.dataset.price_rows.get(product):
            source_label = "Price & Trade Data folder"
        elif self.strategy_price_rows.get(product):
            source_label = self.strategy_source_label
        else:
            source_label = "None"
        strategy_status = "None loaded"
        if self.strategy_log_path:
            fill_status = "yes" if self.strategy_has_fill_data else "no"
            quote_status = "yes" if self.strategy_has_quote_data else "no"
            strategy_status = f"{self.strategy_log_path.name} | fills: {fill_status} | quotes: {quote_status}"
        final_position = self.strategy_final_positions.get(product)
        final_position_text = "Unknown" if final_position is None else str(final_position)
        run_profit_text = "Unknown" if self.strategy_run_profit is None else f"{self.strategy_run_profit:.2f}"

        self.summary_label.setText(
            "\n".join(
                [
                    f"Product: {product}",
                    f"Primary source: {source_label}",
                    f"Days loaded: {', '.join(map(str, unique_days))}",
                    f"Price rows: {len(rows)}",
                    f"Trade rows: {trade_count}",
                    f"Own fills shown: {own_fill_count}",
                    f"Own quotes shown: {own_quote_count}",
                    f"Final reported position: {final_position_text}",
                    f"Run profit: {run_profit_text}",
                    f"Average spread: {avg_spread:.3f}",
                    f"Normalization: {self.normalize_combo.currentText()}",
                    f"Downsample: every {self.downsample_spin.value()} row(s)",
                    f"Run archive: {strategy_status}",
                    f"Preset file: {self.settings_path.name}",
                ]
            )
        )


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Prosperity Order Book Visualizer")
    window = MainWindow()
    if window.icon_path is not None:
        app.setWindowIcon(QIcon(str(window.icon_path)))
    window.show()
    QTimer.singleShot(0, window.force_real_maximize)
    QTimer.singleShot(150, window.fix_startup_layout)
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
