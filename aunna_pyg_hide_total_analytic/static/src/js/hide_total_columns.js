(function () {
    "use strict";

    const REPORT_TOKENS = [
        "perdidas y ganancias",
        "profit and loss",
        "profit & loss",
        "profit loss",
        "pyg",
    ];

    let scheduled = false;

    function normalize(value) {
        return String(value || "")
            .normalize("NFD")
            .replace(/[\u0300-\u036f]/g, "")
            .replace(/\s+/g, " ")
            .trim()
            .toLowerCase();
    }

    function isProfitAndLossPage() {
        const text = normalize(document.body && document.body.textContent);
        return REPORT_TOKENS.some((token) => text.includes(token));
    }

    function directCells(row) {
        return Array.from(row.children).filter((child) =>
            ["TH", "TD"].includes(child.tagName)
        );
    }

    function colspan(cell) {
        const value = parseInt(cell.getAttribute("colspan") || "1", 10);
        return Number.isFinite(value) && value > 0 ? value : 1;
    }

    function rowWidth(row) {
        return directCells(row).reduce((total, cell) => total + colspan(cell), 0);
    }

    function isTotalCell(cell) {
        return normalize(cell.textContent) === "total";
    }

    function totalColumns(table) {
        const indices = new Set();
        let referenceWidth = 0;

        for (const row of table.querySelectorAll("tr")) {
            let position = 0;
            const rowIndices = [];

            for (const cell of directCells(row)) {
                const span = colspan(cell);
                if (isTotalCell(cell)) {
                    for (let index = position; index < position + span; index++) {
                        rowIndices.push(index);
                    }
                }
                position += span;
            }

            if (rowIndices.length) {
                referenceWidth = Math.max(referenceWidth, position);
                for (const index of rowIndices) {
                    indices.add(index);
                }
            }
        }

        return {
            indices: Array.from(indices).sort((a, b) => a - b),
            referenceWidth,
        };
    }

    function shiftedColumns(indices, shift) {
        return new Set(indices.map((index) => index + shift));
    }

    function removeColumnsFromRow(row, columns) {
        let position = 0;

        for (const cell of directCells(row)) {
            const span = colspan(cell);
            let removed = 0;

            for (let index = position; index < position + span; index++) {
                if (columns.has(index)) {
                    removed++;
                }
            }
            position += span;

            if (!removed) {
                continue;
            }
            if (removed >= span) {
                cell.remove();
                continue;
            }

            const newColspan = span - removed;
            if (newColspan > 1) {
                cell.setAttribute("colspan", String(newColspan));
            } else {
                cell.removeAttribute("colspan");
            }
        }
    }

    function removeTotalColumnsFromTable(table) {
        const columns = totalColumns(table);
        if (!columns.indices.length || !columns.referenceWidth) {
            return;
        }

        for (const row of table.querySelectorAll("tr")) {
            const width = rowWidth(row);
            const shift = Math.max(0, width - columns.referenceWidth);
            removeColumnsFromRow(row, shiftedColumns(columns.indices, shift));
        }
    }

    function hideTotalColumns() {
        scheduled = false;
        if (!document.body || !isProfitAndLossPage()) {
            return;
        }

        document.body.dataset.aunnaPygHideTotalLoaded = "1";
        for (const table of document.querySelectorAll("table")) {
            removeTotalColumnsFromTable(table);
        }
    }

    function scheduleHideTotalColumns() {
        if (scheduled) {
            return;
        }
        scheduled = true;
        window.requestAnimationFrame(hideTotalColumns);
    }

    function startObserver() {
        scheduleHideTotalColumns();
        setTimeout(scheduleHideTotalColumns, 100);
        setTimeout(scheduleHideTotalColumns, 500);
        setTimeout(scheduleHideTotalColumns, 1000);

        new MutationObserver(scheduleHideTotalColumns).observe(document.body, {
            childList: true,
            subtree: true,
        });
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", startObserver, { once: true });
    } else {
        startObserver();
    }
})();
