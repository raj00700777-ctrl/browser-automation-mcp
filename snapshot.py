"""
Raj Browser MCP — DOM Tree + Interactive Element Flat List
"""

from browser import browser


async def dom_snapshot():
    try:
        page = await browser.get_page()
        snapshot = await page.evaluate("""
            () => {
                let nodeCount = 0;
                const MAX_NODES = 3000;
                function buildTree(el, depth = 0) {
                    nodeCount++;
                    if (depth > 10 || nodeCount > MAX_NODES) {
                        return { tag: el.tagName, truncated: true };
                    }
                    const node = {
                        tag: el.tagName.toLowerCase(),
                        id: el.id || null,
                        class: el.className || null,
                        text: (el.innerText || '').slice(0, 100),
                        children: [],
                    };
                    for (const child of el.children) {
                        if (nodeCount > MAX_NODES) {
                            node.truncated = true;
                            break;
                        }
                        if (child.tagName) {
                            node.children.push(buildTree(child, depth + 1));
                        }
                    }
                    // Pierce open shadow roots -- web components hide
                    // their real markup here, invisible to el.children.
                    if (el.shadowRoot) {
                        for (const shadowChild of el.shadowRoot.children) {
                            if (nodeCount > MAX_NODES) {
                                node.truncated = true;
                                break;
                            }
                            const built = buildTree(shadowChild, depth + 1);
                            built.in_shadow_dom = true;
                            node.children.push(built);
                        }
                    }
                    return node;
                }
                return buildTree(document.body);
            }
        """)
        return {"success": True, "snapshot": snapshot}
    except Exception as e:
        return {"success": False, "error": str(e)}


async def interactive_snapshot():
    try:
        page = await browser.get_page()
        elements = await page.evaluate("""
            () => {
                const selectors = 'a, button, input, textarea, select, [role="button"], [role="link"], [onclick], [tabindex]:not([tabindex="-1"])';

                function collect(root, inShadow) {
                    const found = Array.from(root.querySelectorAll(selectors))
                        .map(el => ({ el, inShadow }));

                    // Recurse into every open shadow root under this
                    // root too, so components like Lit/Stencil/Shoelace
                    // based widgets (chat boxes, custom dropdowns,
                    // checkout forms) aren't invisible to this tool.
                    const allEls = root.querySelectorAll('*');
                    for (const el of allEls) {
                        if (el.shadowRoot) {
                            found.push(...collect(el.shadowRoot, true));
                        }
                    }
                    return found;
                }

                return collect(document, false).map(({ el, inShadow }, i) => {
                    const rect = el.getBoundingClientRect();
                    return {
                        index: i,
                        tag: el.tagName.toLowerCase(),
                        type: el.type || null,
                        id: el.id || null,
                        name: el.getAttribute('name') || null,
                        class: el.className || null,
                        text: (el.innerText || el.value || el.placeholder || '').slice(0, 50),
                        selector: el.id ? '#' + el.id : 
                                  el.getAttribute('name') ? `[name="${el.getAttribute('name')}"]` :
                                  el.className ? '.' + el.className.split(' ')[0] : 
                                  el.tagName.toLowerCase(),
                        x: Math.round(rect.left + rect.width / 2),
                        y: Math.round(rect.top + rect.height / 2),
                        width: Math.round(rect.width),
                        height: Math.round(rect.height),
                        visible: rect.width > 0 && rect.height > 0,
                        in_shadow_dom: inShadow,
                    };
                }).filter(e => e.visible);
            }
        """)
        return {"success": True, "elements": elements, "count": len(elements)}
    except Exception as e:
        return {"success": False, "error": str(e)}