package dev.qoralo.podcast.e2e;

import java.util.ArrayList;
import java.util.List;

/** Safe derived fixture: background breadcrumb, delayed rows, observed two-ancestor row action. */
public final class SafRootReadinessFixture {
    static final class Node {
        final String id, text;
        boolean visible = true, click;
        Node parent;
        final List<Node> children = new ArrayList<>();
        Node(String id, String text) { this.id = id; this.text = text; }
        Node add(Node child) { child.parent = this; children.add(child); return child; }
    }
    static final SafRootReadiness.Nodes<Node> NODES = new SafRootReadiness.Nodes<Node>() {
        public String id(Node n) { return n.id; }
        public String text(Node n) { return n.text; }
        public boolean visible(Node n) { return n.visible; }
        public boolean canClick(Node n) { return n.click; }
        public Node parent(Node n) { return n.parent; }
        public List<Node> children(Node n) { return n.children; }
    };
    static void check(boolean value, String why) { if (!value) throw new AssertionError(why); }
    public static void main(String[] args) {
        Node root = new Node("window", null);
        root.add(new Node("breadcrumb_text", "Downloads"));
        check(SafRootReadiness.downloadsAction(root, NODES) == null, "breadcrumb is NOT drawer readiness");
        Node list = root.add(new Node("com.google.android.documentsui:id/roots_list", null));
        check(SafRootReadiness.downloadsAction(root, NODES) == null, "empty async list is NOT readiness");
        Node row = list.add(new Node(null, null)); row.click = true;
        Node container = row.add(new Node(null, null));
        Node title = container.add(new Node("android:id/title", "Downloads"));
        check(SafRootReadiness.downloadsAction(root, NODES) == row, "actual clickable grandparent must be returned");
        title.visible = false;
        check(SafRootReadiness.downloadsAction(root, NODES) == null, "hidden title is not ready"); title.visible = true;
        list.visible = false;
        check(SafRootReadiness.downloadsAction(root, NODES) == null, "hidden list is not ready"); list.visible = true;
        row.click = false; list.click = true;
        check(SafRootReadiness.downloadsAction(root, NODES) == null, "must never click list/container as row fallback"); row.click = true;
        list.add(new Node("android:id/title", "Downloads"));
        check(SafRootReadiness.downloadsAction(root, NODES) == null, "ambiguous duplicate root must remain unready");
        System.out.println("7 actual shared-predicate fixtures PASS; no Android/model calls");
    }
}
