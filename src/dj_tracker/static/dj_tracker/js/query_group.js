class QueryNode {
    constructor(node) {
        this.node = node;
        this.sqlID = node.dataset.sqlId;
        this.tracebackID = node.dataset.tracebackId;
        this.relatedCount = parseInt(node.dataset.related);
        this.duplicate = JSON.parse(node.dataset.duplicate.toLowerCase());
    }

    show() {
        this.node.style.display = "";
    }

    hide() {
        this.node.style.display = "none";
    }
}

class QueryGroup {
    constructor() {
        this.shown = new Set(
            Array.from(
                document.querySelectorAll("[data-depth='0']"),
                (node) => new QueryNode(node)
            )
        );
        this.hidden = new Set();
        this.value = null;

        const radios = document.forms[0].elements["select"];
        radios.forEach((radio) => {
            let showNode;

            switch (radio.dataset.selectType) {
                case "related":
                    showNode = (node) => node.relatedCount;
                    break;
                case "duplicates":
                    showNode = (node) => node.duplicate;
                    break;
                case "sql":
                    showNode = (node) => node.sqlID === radio.value;
                    break;
                case "traceback":
                    showNode = (node) => node.tracebackID === radio.value;
                    break;
                default:
                    throw new Error("Unknown select type.");
            }

            radio.onclick = (e) => this.toggle(e.target, showNode);

            if (radios.value === radio.value) {
                this.toggle(radio, showNode);
            }
        });
    }

    revealAll() {
        this.hidden.forEach((node) => {
            node.show();
            this.shown.add(node);
        });

        this.hidden.clear();
        this.value = null;
    }

    toggle(target, showNode) {
        if (target.value === this.value) {
            target.checked = false;
            this.revealAll();
            return;
        }

        const hidden = new Set();

        this.shown.forEach((node) => {
            if (!showNode(node)) {
                node.hide();
                this.shown.delete(node);
                hidden.add(node);
            }
        });

        this.hidden.forEach((node) => {
            if (showNode(node)) {
                node.show();
                this.hidden.delete(node);
                this.shown.add(node);
            }
        });

        hidden.forEach((node) => this.hidden.add(node));
        this.value = target.value;
    }
}

window.onload = (e) => new QueryGroup();
