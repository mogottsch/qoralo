package dev.qoralo.podcast.e2e;

import java.util.ArrayList;
import java.util.List;
import java.util.Objects;

/** Pure test-driver predicate, shared verbatim with a JVM delayed-drawer fixture. */
public final class SafRootReadiness {
    private SafRootReadiness() {}
    public interface Nodes<T> {
        String id(T node);
        String text(T node);
        boolean visible(T node);
        boolean canClick(T node);
        T parent(T node);
        List<T> children(T node);
    }
    private static <T> List<T> walk(T node, Nodes<T> nodes) {
        List<T> result = new ArrayList<>();
        if (node != null) {
            result.add(node);
            for (T child : nodes.children(node)) result.addAll(walk(child, nodes));
        }
        return result;
    }
    public static <T> T downloadsAction(T freshRoot, Nodes<T> nodes) {
        T list = null;
        for (T node : walk(freshRoot, nodes)) {
            String id = nodes.id(node);
            if (nodes.visible(node) && id != null && id.endsWith(":id/roots_list")) {
                if (list != null) return null;
                list = node;
            }
        }
        if (list == null) return null;
        T title = null;
        for (T node : walk(list, nodes)) {
            if (nodes.visible(node) && "android:id/title".equals(nodes.id(node)) && "Downloads".equals(nodes.text(node))) {
                if (title != null) return null;
                title = node;
            }
        }
        if (title == null) return null;
        T action = title;
        while (action != null && !Objects.equals(action, list) && !nodes.canClick(action)) action = nodes.parent(action);
        return action != null && !Objects.equals(action, list) && nodes.visible(action) ? action : null;
    }
}
