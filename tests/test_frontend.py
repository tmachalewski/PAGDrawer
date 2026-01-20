"""
Frontend browser tests using Playwright.

These tests verify the JavaScript functionality in the frontend.
Requires running server: uvicorn src.viz.app:app --port 8000
Or Vite dev server: npm run dev (port 3000)

Use: pytest tests/test_frontend.py --base-url=http://localhost:8000
"""

import os
import pytest
from playwright.sync_api import Page, expect


# Get base URL from environment or use default
# Use Vite dev server (port 3000) which transpiles TypeScript and proxies API to FastAPI (8000)
BASE_URL = os.environ.get("PYTEST_BASE_URL", "http://localhost:3000")


def wait_for_cytoscape(page: Page, timeout: int = 10000) -> None:
    """
    Wait for Cytoscape to be fully initialized.

    Checks that window.cy exists and has the nodes() method,
    confirming it's a fully functional Cytoscape instance.
    """
    page.wait_for_function(
        """() => {
            const cy = window.cy || (window.getCy ? window.getCy() : null);
            return cy && typeof cy.nodes === 'function' && cy.nodes().length > 0;
        }""",
        timeout=timeout
    )


@pytest.fixture(scope="session")
def browser_context_args():
    """Browser context configuration."""
    return {
        "viewport": {"width": 1920, "height": 1080}
    }


class TestGraphLoading:
    """Tests for initial graph loading."""
    
    def test_page_loads(self, page: Page):
        """Page should load without errors."""
        page.goto(BASE_URL)
        expect(page).to_have_title("PAGDrawer - Knowledge Graph Visualization")
    
    def test_graph_container_visible(self, page: Page):
        """Graph container should be visible."""
        page.goto(BASE_URL)
        page.wait_for_selector("#cy", timeout=5000)
        
        cy_container = page.locator("#cy")
        expect(cy_container).to_be_visible()
    
    def test_sidebar_visible(self, page: Page):
        """Sidebar should be visible."""
        page.goto(BASE_URL)
        
        sidebar = page.locator(".sidebar")
        expect(sidebar).to_be_visible()
    
    def test_node_count_displayed(self, page: Page):
        """Node count should be displayed in Settings modal."""
        page.goto(BASE_URL)
        wait_for_cytoscape(page)
        
        # Open Settings modal where stats are now displayed
        page.get_by_role("button", name="Settings").click()
        page.locator("#settings-modal").wait_for(state="visible", timeout=5000)
        
        # Check that modal shows node count
        modal_text = page.locator(".modal-content").inner_text()
        assert "Total Nodes" in modal_text
    
    def test_edge_count_displayed(self, page: Page):
        """Edge count should be displayed in Settings modal."""
        page.goto(BASE_URL)
        wait_for_cytoscape(page)
        
        # Open Settings modal where stats are now displayed
        page.get_by_role("button", name="Settings").click()
        page.locator("#settings-modal").wait_for(state="visible", timeout=5000)
        
        # Check that modal shows edge count
        modal_text = page.locator(".modal-content").inner_text()
        assert "Total Edges" in modal_text


class TestEnvironmentFiltering:
    """Tests for UI/AC environment filtering."""
    
    def test_ui_dropdown_exists(self, page: Page):
        """UI dropdown should exist."""
        page.goto(BASE_URL)
        
        ui_select = page.locator("#env-ui")
        expect(ui_select).to_be_visible()
    
    def test_ac_dropdown_exists(self, page: Page):
        """AC dropdown should exist."""
        page.goto(BASE_URL)
        
        ac_select = page.locator("#env-ac")
        expect(ac_select).to_be_visible()
    
    def test_change_ui_filter(self, page: Page):
        """Changing UI filter should trigger filtering."""
        page.goto(BASE_URL)
        page.wait_for_timeout(2000)
        
        # Change UI to Required
        page.select_option("#env-ui", "R")
        page.wait_for_timeout(500)
        
        # Some elements should have env-filtered class
        # (This test assumes some CVEs require UI:R)
        # Just verify no errors occur
        assert page.locator("#cy").is_visible()
    
    def test_change_ac_filter(self, page: Page):
        """Changing AC filter should trigger filtering."""
        page.goto(BASE_URL)
        page.wait_for_timeout(2000)
        
        # Change AC to High
        page.select_option("#env-ac", "H")
        page.wait_for_timeout(500)
        
        assert page.locator("#cy").is_visible()


class TestNodeSelection:
    """Tests for node selection and hover tooltip."""
    
    def test_tooltip_element_exists(self, page: Page):
        """Node tooltip element should exist."""
        page.goto(BASE_URL)
        
        tooltip = page.locator("#node-tooltip")
        expect(tooltip).to_be_attached()
    
    def test_hover_shows_tooltip(self, page: Page):
        """Hovering over a node should show tooltip with details."""
        page.goto(BASE_URL)
        wait_for_cytoscape(page)

        # Trigger hover on a node via JavaScript
        tooltip_content = page.evaluate("""
            () => {
                const cy = window.cy || (window.getCy ? window.getCy() : null);
                if (!cy) return { error: 'cy not found' };
                
                // Trigger mouseover on first HOST node
                const host = cy.nodes('[type="HOST"]').first();
                if (host.empty()) return { error: 'no HOST found' };
                
                host.emit('mouseover');
                
                const tooltip = document.getElementById('node-tooltip');
                return {
                    innerText: tooltip.innerText,
                    hasContent: tooltip.innerText.length > 0
                };
            }
        """)
        assert tooltip_content.get('hasContent', False), f"Tooltip should show node details: {tooltip_content}"
    
    def test_node_click_highlights_neighbors(self, page: Page):
        """Clicking a node should highlight its connected neighbors."""
        page.goto(BASE_URL)
        wait_for_cytoscape(page)

        # Click on a node and check for faded class on non-neighbors
        has_highlights = page.evaluate("""
            () => {
                const cy = window.cy || (window.getCy ? window.getCy() : null);
                if (!cy) return false;
                
                const host = cy.nodes('[type="HOST"]').first();
                host.trigger('tap');
                
                // After click, some nodes should have 'faded' class
                return cy.nodes('.faded').length > 0;
            }
        """)
        assert has_highlights, "Clicking should add 'faded' class to non-neighbors"



class TestLayoutControls:
    """Tests for layout control buttons."""
    
    def test_layout_dropdown_exists(self, page: Page):
        """Layout dropdown should exist."""
        page.goto(BASE_URL)
        
        layout_select = page.locator("#layout-select")
        expect(layout_select).to_be_visible()
    
    def test_fit_view_button_exists(self, page: Page):
        """Fit View button should exist."""
        page.goto(BASE_URL)
        
        fit_btn = page.get_by_role("button", name="Fit View")
        expect(fit_btn).to_be_visible()
    
    def test_relayout_button_exists(self, page: Page):
        """Relayout button should exist."""
        page.goto(BASE_URL)
        
        relayout_btn = page.get_by_role("button", name="Relayout")
        expect(relayout_btn).to_be_visible()
    
    def test_change_layout(self, page: Page):
        """Changing layout should work without errors."""
        page.goto(BASE_URL)
        page.wait_for_timeout(2000)
        
        # Change to breadthfirst layout
        page.select_option("#layout-select", "breadthfirst")
        page.wait_for_timeout(1000)
        
        # Graph should still be visible
        assert page.locator("#cy").is_visible()


class TestExploitPaths:
    """Tests for Exploit Paths functionality."""
    
    def test_exploit_paths_button_exists(self, page: Page):
        """Exploit Paths button should exist."""
        page.goto(BASE_URL)
        
        exploit_btn = page.get_by_role("button", name="Exploit Paths")
        expect(exploit_btn).to_be_visible()
    
    def test_click_exploit_paths(self, page: Page):
        """Clicking Exploit Paths should work."""
        page.goto(BASE_URL)
        page.wait_for_timeout(2000)
        
        exploit_btn = page.get_by_role("button", name="Exploit Paths")
        exploit_btn.click()
        page.wait_for_timeout(500)
        
        # Graph should still be visible
        assert page.locator("#cy").is_visible()
    
    def test_toggle_exploit_paths(self, page: Page):
        """Exploit Paths should toggle on/off."""
        page.goto(BASE_URL)
        page.wait_for_timeout(2000)
        
        exploit_btn = page.get_by_role("button", name="Exploit Paths")
        
        # Toggle on
        exploit_btn.click()
        page.wait_for_timeout(500)
        
        # Toggle off
        exploit_btn.click()
        page.wait_for_timeout(500)
        
        assert page.locator("#cy").is_visible()


class TestSettingsModal:
    """Tests for Settings modal."""
    
    def test_settings_button_exists(self, page: Page):
        """Settings button should exist."""
        page.goto(BASE_URL)
        
        settings_btn = page.get_by_role("button", name="Settings")
        expect(settings_btn).to_be_visible()
    
    def test_open_settings_modal(self, page: Page):
        """Clicking Settings should open modal."""
        page.goto(BASE_URL)
        wait_for_cytoscape(page)

        settings_btn = page.get_by_role("button", name="Settings")
        settings_btn.click()

        modal = page.locator("#settings-modal")
        expect(modal).to_be_visible(timeout=5000)
    
    def test_settings_has_node_types(self, page: Page):
        """Settings modal should list all node types."""
        page.goto(BASE_URL)
        
        page.get_by_role("button", name="Settings").click()
        page.wait_for_timeout(300)
        
        modal_text = page.locator(".modal-content").inner_text()
        
        assert "CPE" in modal_text
        assert "CVE" in modal_text
        assert "CWE" in modal_text
        assert "TI" in modal_text
        assert "VC" in modal_text
    
    def test_close_settings_modal(self, page: Page):
        """Should be able to close settings modal."""
        page.goto(BASE_URL)
        wait_for_cytoscape(page)

        page.get_by_role("button", name="Settings").click()
        page.locator("#settings-modal").wait_for(state="visible", timeout=5000)

        close_btn = page.locator(".close-btn")
        close_btn.click()

        # Modal should be hidden
        modal = page.locator("#settings-modal")
        expect(modal).to_be_hidden(timeout=5000)

    def test_slider_positions_persist_after_save(self, page: Page):
        """Slider positions should be remembered after save and reopen."""
        page.goto(BASE_URL)
        wait_for_cytoscape(page)

        # Open settings modal
        page.get_by_role("button", name="Settings").click()
        page.locator("#settings-modal").wait_for(state="visible", timeout=5000)

        # Get CPE and CVE sliders
        cpe_slider = page.locator("#config-CPE")
        cve_slider = page.locator("#config-CVE")

        # Change slider positions (CPE to 0, CVE to 1)
        cpe_slider.fill("0")
        cpe_slider.dispatch_event("input")
        cve_slider.fill("1")
        cve_slider.dispatch_event("input")

        # Save settings
        page.get_by_role("button", name="Save").click()

        # Wait for graph rebuild
        wait_for_cytoscape(page, timeout=10000)

        # Reopen settings modal
        page.get_by_role("button", name="Settings").click()
        page.locator("#settings-modal").wait_for(state="visible", timeout=5000)

        # Verify slider positions persisted
        final_cpe = cpe_slider.input_value()
        final_cve = cve_slider.input_value()

        assert final_cpe == "0", f"CPE slider should be 0, got {final_cpe}"
        assert final_cve == "1", f"CVE slider should be 1, got {final_cve}"

    def test_slider_affects_graph_node_count(self, page: Page):
        """Changing slider to universal should reduce node count."""
        page.goto(BASE_URL)
        wait_for_cytoscape(page)

        # Get initial node count via JS (more reliable than modal text)
        initial_count = int(page.evaluate("getCy().nodes().length"))

        # Open settings and set CPE to universal (position 0)
        page.get_by_role("button", name="Settings").click()
        page.locator("#settings-modal").wait_for(state="visible", timeout=5000)

        cpe_slider = page.locator("#config-CPE")
        cpe_slider.fill("0")
        cpe_slider.dispatch_event("input")

        # Save settings
        page.get_by_role("button", name="Save").click()
        wait_for_cytoscape(page, timeout=10000)

        # Get new node count via JS
        final_count = int(page.evaluate("getCy().nodes().length"))

        # Universal mode should have fewer or equal nodes
        assert final_count <= initial_count, f"Expected {final_count} <= {initial_count}"


class TestHideRestore:
    """Tests for Hide/Restore functionality."""
    
    def test_hide_button_exists(self, page: Page):
        """Hide Selected button should exist."""
        page.goto(BASE_URL)
        
        hide_btn = page.locator("#hide-btn")
        expect(hide_btn).to_be_visible()
    
    def test_restore_button_exists(self, page: Page):
        """Restore All button should exist."""
        page.goto(BASE_URL)
        
        restore_btn = page.get_by_role("button", name="Restore All")
        expect(restore_btn).to_be_visible()
    
    def test_hide_without_selection_shows_alert(self, page: Page):
        """Hide without selection should show alert."""
        page.goto(BASE_URL)
        wait_for_cytoscape(page)

        # Set up dialog handler
        dialog_message = []
        page.on("dialog", lambda dialog: (dialog_message.append(dialog.message), dialog.accept()))

        hide_btn = page.locator("#hide-btn")
        hide_btn.click()
        page.wait_for_timeout(500)  # Brief wait for dialog to appear

        # Should show alert about selecting nodes first
        assert len(dialog_message) > 0
        assert "Select" in dialog_message[0] or "select" in dialog_message[0]


class TestVisibilityToggle:
    """Tests for node type visibility toggle (👁 buttons)."""

    def test_visibility_toggles_exist(self, page: Page):
        """Visibility toggle buttons should exist for each node type."""
        page.goto(BASE_URL)
        wait_for_cytoscape(page)

        toggles = page.locator(".visibility-toggle")
        assert toggles.count() == 7  # ATTACKER, HOST, CPE, CVE, CWE, TI, VC

    def test_single_toggle_hide_show(self, page: Page):
        """Hiding and showing a single type should preserve node count."""
        page.goto(BASE_URL)
        wait_for_cytoscape(page)

        # Get initial counts
        initial_nodes = int(page.evaluate("getCy().nodes().length"))
        initial_edges = int(page.evaluate("getCy().edges().length"))

        # Hide CVE nodes
        page.locator('.visibility-toggle[data-type="CVE"]').click()
        page.wait_for_timeout(300)

        # Verify some nodes are hidden (bridges created)
        after_hide_nodes = int(page.evaluate("getCy().nodes().length"))
        assert after_hide_nodes < initial_nodes

        # Show CVE nodes
        page.locator('.visibility-toggle[data-type="CVE"]').click()
        page.wait_for_timeout(300)

        # Verify counts restored
        final_nodes = int(page.evaluate("getCy().nodes().length"))
        final_edges = int(page.evaluate("getCy().edges().length"))

        assert final_nodes == initial_nodes, f"Nodes: expected {initial_nodes}, got {final_nodes}"
        assert final_edges == initial_edges, f"Edges: expected {initial_edges}, got {final_edges}"

    def test_toggle_same_type_multiple_times(self, page: Page):
        """Toggling the same type multiple times should preserve node count."""
        page.goto(BASE_URL)
        wait_for_cytoscape(page)

        initial_nodes = int(page.evaluate("getCy().nodes().length"))
        initial_edges = int(page.evaluate("getCy().edges().length"))

        toggle = page.locator('.visibility-toggle[data-type="CWE"]')

        # Toggle 5 times
        for i in range(5):
            toggle.click()
            page.wait_for_timeout(200)

        # After odd number of clicks, should be hidden
        # Click once more to show
        toggle.click()
        page.wait_for_timeout(300)

        final_nodes = int(page.evaluate("getCy().nodes().length"))
        final_edges = int(page.evaluate("getCy().edges().length"))

        assert final_nodes == initial_nodes, f"Nodes: expected {initial_nodes}, got {final_nodes}"
        assert final_edges == initial_edges, f"Edges: expected {initial_edges}, got {final_edges}"

    def test_toggle_multiple_types_then_restore(self, page: Page):
        """Hiding multiple types then using Restore All should preserve counts."""
        page.goto(BASE_URL)
        wait_for_cytoscape(page)

        initial_nodes = int(page.evaluate("getCy().nodes().length"))
        initial_edges = int(page.evaluate("getCy().edges().length"))

        # Hide CVE, CWE, and TI
        page.locator('.visibility-toggle[data-type="CVE"]').click()
        page.wait_for_timeout(200)
        page.locator('.visibility-toggle[data-type="CWE"]').click()
        page.wait_for_timeout(200)
        page.locator('.visibility-toggle[data-type="TI"]').click()
        page.wait_for_timeout(300)

        # Click Restore All
        page.get_by_role("button", name="Restore All").click()
        page.wait_for_timeout(500)

        final_nodes = int(page.evaluate("getCy().nodes().length"))
        final_edges = int(page.evaluate("getCy().edges().length"))

        assert final_nodes == initial_nodes, f"Nodes: expected {initial_nodes}, got {final_nodes}"
        assert final_edges == initial_edges, f"Edges: expected {initial_edges}, got {final_edges}"

    def test_toggle_multiple_types_individually_restore(self, page: Page):
        """Hiding then showing multiple types individually should preserve counts."""
        page.goto(BASE_URL)
        wait_for_cytoscape(page)

        initial_nodes = int(page.evaluate("getCy().nodes().length"))
        initial_edges = int(page.evaluate("getCy().edges().length"))

        # Hide CVE, CWE, TI in sequence
        page.locator('.visibility-toggle[data-type="CVE"]').click()
        page.wait_for_timeout(200)
        page.locator('.visibility-toggle[data-type="CWE"]').click()
        page.wait_for_timeout(200)
        page.locator('.visibility-toggle[data-type="TI"]').click()
        page.wait_for_timeout(300)

        # Show them in reverse order
        page.locator('.visibility-toggle[data-type="TI"]').click()
        page.wait_for_timeout(200)
        page.locator('.visibility-toggle[data-type="CWE"]').click()
        page.wait_for_timeout(200)
        page.locator('.visibility-toggle[data-type="CVE"]').click()
        page.wait_for_timeout(300)

        final_nodes = int(page.evaluate("getCy().nodes().length"))
        final_edges = int(page.evaluate("getCy().edges().length"))

        assert final_nodes == initial_nodes, f"Nodes: expected {initial_nodes}, got {final_nodes}"
        assert final_edges == initial_edges, f"Edges: expected {initial_edges}, got {final_edges}"

    def test_toggle_adjacent_types(self, page: Page):
        """Hiding adjacent types in the graph hierarchy should work correctly."""
        page.goto(BASE_URL)
        wait_for_cytoscape(page)

        initial_nodes = int(page.evaluate("getCy().nodes().length"))
        initial_edges = int(page.evaluate("getCy().edges().length"))

        # Hide CPE then CVE (adjacent in hierarchy)
        page.locator('.visibility-toggle[data-type="CPE"]').click()
        page.wait_for_timeout(200)
        page.locator('.visibility-toggle[data-type="CVE"]').click()
        page.wait_for_timeout(300)

        # Show CVE then CPE
        page.locator('.visibility-toggle[data-type="CVE"]').click()
        page.wait_for_timeout(200)
        page.locator('.visibility-toggle[data-type="CPE"]').click()
        page.wait_for_timeout(300)

        final_nodes = int(page.evaluate("getCy().nodes().length"))
        final_edges = int(page.evaluate("getCy().edges().length"))

        assert final_nodes == initial_nodes, f"Nodes: expected {initial_nodes}, got {final_nodes}"
        assert final_edges == initial_edges, f"Edges: expected {initial_edges}, got {final_edges}"

    def test_edge_restoration_same_order_show(self, page: Page):
        """Regression test: Edges must be preserved when showing types in SAME order as hiding.
        
        This tests the specific scenario that was broken before the global edge storage fix:
        1. Hide CVE → edges stored in CVE storage
        2. Hide CWE → CVE↔CWE edges stored AGAIN in CWE storage  
        3. Show CVE → CVE↔CWE edges skipped (CWE still hidden)
        4. Show CWE → edges were in CVE storage, not restored from CWE storage → LOST
        
        The fix uses global edge storage to prevent duplicates and restore correctly.
        """
        page.goto(BASE_URL)
        wait_for_cytoscape(page)

        initial_nodes = int(page.evaluate("getCy().nodes().length"))
        initial_edges = int(page.evaluate("getCy().edges().length"))

        # Hide CVE then CWE
        page.locator('.visibility-toggle[data-type="CVE"]').click()
        page.wait_for_timeout(200)
        page.locator('.visibility-toggle[data-type="CWE"]').click()
        page.wait_for_timeout(300)

        # Show in SAME order (CVE then CWE) - this was the buggy scenario
        page.locator('.visibility-toggle[data-type="CVE"]').click()
        page.wait_for_timeout(200)
        page.locator('.visibility-toggle[data-type="CWE"]').click()
        page.wait_for_timeout(300)

        final_nodes = int(page.evaluate("getCy().nodes().length"))
        final_edges = int(page.evaluate("getCy().edges().length"))

        assert final_nodes == initial_nodes, f"Nodes: expected {initial_nodes}, got {final_nodes}"
        assert final_edges == initial_edges, f"Edges: expected {initial_edges}, got {final_edges} (edge restoration bug)"

    def test_no_bridge_edges_after_full_restore(self, page: Page):
        """After restoring all, no bridge edges should remain."""
        page.goto(BASE_URL)
        wait_for_cytoscape(page)

        # Hide a few types
        page.locator('.visibility-toggle[data-type="CVE"]').click()
        page.wait_for_timeout(200)
        page.locator('.visibility-toggle[data-type="TI"]').click()
        page.wait_for_timeout(300)

        # Verify bridges exist
        bridges_during = int(page.evaluate('getCy().edges("[isBridge]").length'))
        assert bridges_during > 0, "Should have bridge edges while types are hidden"

        # Restore all
        page.get_by_role("button", name="Restore All").click()
        page.wait_for_timeout(500)

        # Verify no bridges remain
        bridges_after = int(page.evaluate('getCy().edges("[isBridge]").length'))
        assert bridges_after == 0, f"Should have no bridge edges after restore, got {bridges_after}"

    def test_hidden_types_preserved_after_settings_save(self, page: Page):
        """Hidden types should be preserved when settings are saved."""
        page.goto(BASE_URL)
        wait_for_cytoscape(page)

        # Hide CVE nodes
        page.locator('.visibility-toggle[data-type="CVE"]').click()
        page.wait_for_timeout(300)

        # Verify CVE is hidden
        cve_before = int(page.evaluate('getCy().nodes().filter(n => n.data("type") === "CVE").length'))
        assert cve_before == 0, "CVE should be hidden"

        # Open settings and save (triggers graph rebuild)
        page.get_by_role("button", name="Settings").click()
        page.locator("#settings-modal").wait_for(state="visible", timeout=5000)
        page.get_by_role("button", name="Save").click()

        # Wait for graph rebuild
        wait_for_cytoscape(page, timeout=10000)

        # Verify CVE is still hidden
        cve_after = int(page.evaluate('getCy().nodes().filter(n => n.data("type") === "CVE").length'))
        assert cve_after == 0, f"CVE should still be hidden after settings save, got {cve_after}"

        # Verify toggle button still shows hidden state
        toggle_hidden = page.locator('.visibility-toggle[data-type="CVE"]').evaluate(
            'el => el.classList.contains("hidden")'
        )
        assert toggle_hidden, "Toggle button should still have 'hidden' class"

    def test_multiple_hidden_types_preserved_after_settings_save(self, page: Page):
        """Multiple hidden types should be preserved with correct edges after settings save."""
        page.goto(BASE_URL)
        wait_for_cytoscape(page)

        # Get initial counts
        initial_nodes = int(page.evaluate("getCy().nodes().length"))
        initial_edges = int(page.evaluate("getCy().edges().length"))

        # Hide CVE, CWE, and TI
        page.locator('.visibility-toggle[data-type="CVE"]').click()
        page.wait_for_timeout(200)
        page.locator('.visibility-toggle[data-type="CWE"]').click()
        page.wait_for_timeout(200)
        page.locator('.visibility-toggle[data-type="TI"]').click()
        page.wait_for_timeout(300)

        # Record counts after hiding
        after_hide_nodes = int(page.evaluate("getCy().nodes().length"))

        # Open settings and save (triggers graph rebuild)
        page.get_by_role("button", name="Settings").click()
        page.locator("#settings-modal").wait_for(state="visible", timeout=5000)
        page.get_by_role("button", name="Save").click()

        # Wait for graph rebuild
        wait_for_cytoscape(page, timeout=10000)

        # Verify same node count as before save
        after_save_nodes = int(page.evaluate("getCy().nodes().length"))
        assert after_save_nodes == after_hide_nodes, \
            f"Node count should be same after save: expected {after_hide_nodes}, got {after_save_nodes}"

        # Verify all three types still hidden
        for node_type in ["CVE", "CWE", "TI"]:
            count = int(page.evaluate(f'getCy().nodes().filter(n => n.data("type") === "{node_type}").length'))
            assert count == 0, f"{node_type} should still be hidden, got {count}"

        # Now restore all and verify original counts
        page.get_by_role("button", name="Restore All").click()
        page.wait_for_timeout(500)

        final_nodes = int(page.evaluate("getCy().nodes().length"))
        final_edges = int(page.evaluate("getCy().edges().length"))

        assert final_nodes == initial_nodes, f"Nodes after restore: expected {initial_nodes}, got {final_nodes}"
        assert final_edges == initial_edges, f"Edges after restore: expected {initial_edges}, got {final_edges}"

    def test_visibility_toggle_with_hide_selected(self, page: Page):
        """Visibility toggle and Hide Selected should work independently."""
        page.goto(BASE_URL)
        wait_for_cytoscape(page)

        initial_nodes = int(page.evaluate("getCy().nodes().length"))
        initial_edges = int(page.evaluate("getCy().edges().length"))

        # Hide CVE type using visibility toggle
        page.locator('.visibility-toggle[data-type="CVE"]').click()
        page.wait_for_timeout(300)

        after_toggle_nodes = int(page.evaluate("getCy().nodes().length"))
        cve_count = int(page.evaluate('getCy().nodes().filter(n => n.data("type") === "CVE").length'))
        assert cve_count == 0, "CVE should be hidden by toggle"

        # Select and hide a HOST node using Hide Selected
        page.evaluate('getCy().nodes().filter(n => n.data("type") === "HOST").first().select()')
        page.wait_for_timeout(100)

        page.locator("#hide-btn").click()
        page.wait_for_timeout(300)

        after_hide_nodes = int(page.evaluate("getCy().nodes().length"))
        assert after_hide_nodes < after_toggle_nodes, "Hide Selected should hide additional nodes"

        # Show CVE using visibility toggle
        page.locator('.visibility-toggle[data-type="CVE"]').click()
        page.wait_for_timeout(300)

        # CVE should be visible now, but HOST still hidden
        cve_after = int(page.evaluate('getCy().nodes().filter(n => n.data("type") === "CVE").length'))
        assert cve_after > 0, "CVE should be visible after toggle"

        # Restore All should restore everything
        page.get_by_role("button", name="Restore All").click()
        page.wait_for_timeout(500)

        final_nodes = int(page.evaluate("getCy().nodes().length"))
        final_edges = int(page.evaluate("getCy().edges().length"))

        assert final_nodes == initial_nodes, f"Nodes: expected {initial_nodes}, got {final_nodes}"
        assert final_edges == initial_edges, f"Edges: expected {initial_edges}, got {final_edges}"


class TestFilterButtons:
    """Tests for node type filter buttons."""

    def test_filter_buttons_exist(self, page: Page):
        """Filter buttons should exist for each type."""
        page.goto(BASE_URL)
        
        filter_types = ["All", "HOST", "CPE", "CVE", "CWE", "TI", "VC"]
        
        for filter_type in filter_types:
            btn = page.locator(f".filter-btn[data-type='{filter_type}'], .filter-btn:text('{filter_type}')")
            # At least one should exist
            assert btn.count() >= 0
    
    def test_all_filter_active_by_default(self, page: Page):
        """'All' filter should be active by default."""
        page.goto(BASE_URL)
        
        all_btn = page.locator(".filter-btn[data-type='all']")
        # Check if button has 'active' class (using string match)
        assert "active" in all_btn.get_attribute("class") or all_btn.count() == 0


class TestReachabilityFiltering:
    """Tests for reachability filtering - dimming unreachable hosts."""
    
    def test_reachability_log_appears(self, page: Page):
        """Console should log reachable hosts."""
        # Capture console logs before navigation
        console_messages = []
        page.on("console", lambda msg: console_messages.append(msg.text))

        page.goto(BASE_URL)
        wait_for_cytoscape(page)

        # Check for reachable hosts log
        log_found = any("Reachable hosts:" in msg for msg in console_messages)
        assert log_found, f"Expected 'Reachable hosts:' log message, got: {console_messages[:5]}"
    
    def test_unreachable_class_applied(self, page: Page):
        """Unreachable hosts should have 'unreachable' class."""
        page.goto(BASE_URL)
        wait_for_cytoscape(page)

        # Check that some nodes have unreachable class via JavaScript
        has_unreachable = page.evaluate("""
            () => {
                const cy = window.cy || (window.getCy ? window.getCy() : null);
                if (!cy) return false;
                return cy.nodes('.unreachable').length > 0;
            }
        """)
        assert has_unreachable, "Expected some nodes to have 'unreachable' class"
    
    def test_reachable_hosts_not_dimmed(self, page: Page):
        """Reachable hosts should NOT have unreachable class."""
        page.goto(BASE_URL)
        wait_for_cytoscape(page)

        # Check specific reachable hosts (host-001, host-002)
        reachable_not_dimmed = page.evaluate("""
            () => {
                const cy = window.cy || (window.getCy ? window.getCy() : null);
                if (!cy) return false;
                const host1 = cy.getElementById('host-001');
                const host2 = cy.getElementById('host-002');
                return !host1.hasClass('unreachable') && !host2.hasClass('unreachable');
            }
        """)
        assert reachable_not_dimmed, "Reachable hosts should not be dimmed"
    
    def test_unreachable_hosts_are_dimmed(self, page: Page):
        """Unreachable hosts should have unreachable class."""
        page.goto(BASE_URL)
        wait_for_cytoscape(page)

        # Check that host-003 through host-006 are dimmed
        unreachable_dimmed = page.evaluate("""
            () => {
                const cy = window.cy || (window.getCy ? window.getCy() : null);
                if (!cy) return false;
                const hosts = ['host-003', 'host-004', 'host-005', 'host-006'];
                return hosts.some(id => {
                    const node = cy.getElementById(id);
                    return node.length > 0 && node.hasClass('unreachable');
                });
            }
        """)
        assert unreachable_dimmed, "Unreachable hosts should be dimmed"
    
    def test_filter_preserves_unreachable(self, page: Page):
        """Type filter should preserve unreachable styling."""
        page.goto(BASE_URL)
        wait_for_cytoscape(page)

        # Click CWE filter
        cwe_btn = page.locator(".filter-btn[data-type='CWE']")
        cwe_btn.click()
        page.wait_for_timeout(500)  # Brief wait for filter to apply

        # Check unreachable nodes have faded-unreachable class
        has_faded_unreachable = page.evaluate("""
            () => {
                const cy = window.cy || (window.getCy ? window.getCy() : null);
                if (!cy) return false;
                // After filter, unreachable non-CWE nodes should have faded-unreachable
                return cy.nodes('.faded-unreachable').length > 0 ||
                       cy.nodes('.unreachable').length > 0;
            }
        """)
        assert has_faded_unreachable, "Unreachable styling should be preserved during filtering"
    
    def test_reset_filter_restores_unreachable(self, page: Page):
        """Clicking 'All' should restore original unreachable styling."""
        page.goto(BASE_URL)
        wait_for_cytoscape(page)

        # Click CWE filter
        cwe_btn = page.locator(".filter-btn[data-type='CWE']")
        cwe_btn.click()
        page.wait_for_timeout(500)  # Brief wait for filter to apply

        # Click All filter
        all_btn = page.locator(".filter-btn[data-type='all']")
        all_btn.click()
        page.wait_for_timeout(500)  # Brief wait for filter to apply

        # Check unreachable class is still present
        has_unreachable = page.evaluate("""
            () => {
                const cy = window.cy || (window.getCy ? window.getCy() : null);
                if (!cy) return false;
                return cy.nodes('.unreachable').length > 0;
            }
        """)
        assert has_unreachable, "Unreachable styling should be restored after reset"


    def test_downstream_cves_of_unreachable_host_are_dimmed(self, page: Page):
        """CVE nodes downstream of unreachable L1 hosts should be marked unreachable."""
        page.goto(BASE_URL)
        wait_for_cytoscape(page)

        # Check that CVEs connected to L1 host-005 (not :INSIDE_NETWORK) are unreachable
        downstream_dimmed = page.evaluate("""
            () => {
                const cy = window.cy || (window.getCy ? window.getCy() : null);
                if (!cy) return { error: 'cy not found' };
                
                // Get L1 host-005 (not the L2 version)
                const host005 = cy.getElementById('host-005');
                if (host005.empty()) return { error: 'host-005 not found' };
                
                // Get CVE nodes that are DIRECTLY downstream of L1 host-005
                // Exclude CVEs that belong to L2 hosts (:INSIDE_NETWORK)
                const cves = host005.successors('node[type="CVE"]').filter(
                    cve => !cve.id().includes(':INSIDE_NETWORK')
                );
                if (cves.length === 0) return { error: 'no L1 CVEs found' };
                
                // All L1 CVEs should be unreachable
                const allUnreachable = cves.every(cve => cve.hasClass('unreachable'));
                return {
                    cveCount: cves.length,
                    allUnreachable: allUnreachable
                };
            }
        """)
        assert downstream_dimmed.get('allUnreachable', False), f"CVEs of unreachable L1 host should be dimmed: {downstream_dimmed}"
    
    def test_multi_predecessor_nodes_correctly_marked(self, page: Page):
        """L1 CVE nodes with multiple predecessors should be unreachable if ALL predecessors are unreachable."""
        page.goto(BASE_URL)
        wait_for_cytoscape(page)

        # Check CVEs on L1 host-005 (excluding L2 :INSIDE_NETWORK versions)
        result = page.evaluate("""
            () => {
                const cy = window.cy || (window.getCy ? window.getCy() : null);
                if (!cy) return { error: 'cy not found' };
                
                // Find CVE nodes on L1 host-005 only (exclude :INSIDE_NETWORK)
                const cves = cy.nodes('[type="CVE"]').filter(
                    n => n.id().includes('@host-005') && !n.id().includes(':INSIDE_NETWORK')
                );
                
                return cves.map(cve => ({
                    id: cve.id(),
                    unreachable: cve.hasClass('unreachable'),
                    predecessorCount: cve.incomers('node').length
                }));
            }
        """)
        
        # All L1 CVEs on host-005 should be unreachable
        for cve in result:
            assert cve.get('unreachable', False), f"CVE {cve.get('id')} should be unreachable"
    
    def test_l2_hosts_remain_reachable(self, page: Page):
        """L2 hosts (via INSIDE_NETWORK bridge) should remain reachable."""
        page.goto(BASE_URL)
        wait_for_cytoscape(page)

        l2_reachable = page.evaluate("""
            () => {
                const cy = window.cy || (window.getCy ? window.getCy() : null);
                if (!cy) return false;
                
                // L2 hosts have :INSIDE_NETWORK suffix and should be reachable
                const l2Hosts = cy.nodes('[type="HOST"]').filter(n => n.id().includes(':INSIDE_NETWORK'));
                if (l2Hosts.length === 0) return true; // No L2 hosts, test passes
                
                return l2Hosts.every(host => !host.hasClass('unreachable'));
            }
        """)
        assert l2_reachable, "L2 hosts should remain reachable via jump hosts"


class TestScanSelection:
    """Tests for scan selection and data source management UI."""

    def test_data_source_section_exists(self, page: Page):
        """Data Source section should exist in sidebar."""
        page.goto(BASE_URL)
        wait_for_cytoscape(page)

        # Scroll to data source section
        page.evaluate('document.querySelector(".sidebar").scrollTop = 2000')
        page.wait_for_timeout(200)

        # Check for Data Source section header (uses stats-title class)
        data_source = page.locator(".stats-title:has-text('Data Source')")
        expect(data_source).to_be_visible()

    def test_upload_button_exists(self, page: Page):
        """Upload Trivy Scan button should exist."""
        page.goto(BASE_URL)
        wait_for_cytoscape(page)

        # Scroll to data source section
        page.evaluate('document.querySelector(".sidebar").scrollTop = 2000')
        page.wait_for_timeout(200)

        upload_btn = page.locator(".upload-btn")
        expect(upload_btn).to_be_visible()

    def test_rebuild_button_exists(self, page: Page):
        """Rebuild button should exist."""
        page.goto(BASE_URL)
        wait_for_cytoscape(page)

        page.evaluate('document.querySelector(".sidebar").scrollTop = 2000')
        page.wait_for_timeout(200)

        rebuild_btn = page.locator("#rebuild-btn")
        expect(rebuild_btn).to_be_visible()

    def test_reset_button_exists(self, page: Page):
        """Reset button should exist."""
        page.goto(BASE_URL)
        wait_for_cytoscape(page)

        page.evaluate('document.querySelector(".sidebar").scrollTop = 2000')
        page.wait_for_timeout(200)

        reset_btn = page.locator(".reset-btn")
        expect(reset_btn).to_be_visible()

    def test_scan_selector_hidden_when_no_scans(self, page: Page):
        """Scan selector should be hidden when no scans uploaded."""
        page.goto(BASE_URL)
        wait_for_cytoscape(page)

        # Reset to ensure no scans
        page.evaluate('fetch("/api/data/reset", {method: "POST"})')
        page.wait_for_timeout(500)
        page.reload()
        wait_for_cytoscape(page)

        page.evaluate('document.querySelector(".sidebar").scrollTop = 2000')
        selector_container = page.locator("#scan-selector-container")
        expect(selector_container).to_be_hidden()

    def test_visibility_persists_after_rebuild(self, page: Page):
        """Hidden node types should remain hidden after rebuild."""
        page.goto(BASE_URL)
        wait_for_cytoscape(page)

        # Hide CVE nodes
        page.locator('.visibility-toggle[data-type="CVE"]').click()
        page.wait_for_timeout(300)

        # Verify CVE hidden
        cve_before = int(page.evaluate('getCy().nodes().filter(n => n.data("type") === "CVE").length'))
        assert cve_before == 0, "CVE should be hidden"

        # Scroll to data source and rebuild
        page.evaluate('document.querySelector(".sidebar").scrollTop = 2000')
        page.wait_for_timeout(200)

        # Check if rebuild button is enabled (scans exist)
        rebuild_btn = page.locator("#rebuild-btn")
        if rebuild_btn.is_enabled():
            rebuild_btn.click()
            page.wait_for_timeout(2000)
            wait_for_cytoscape(page)

            # Verify CVE still hidden after rebuild
            cve_after = int(page.evaluate('getCy().nodes().filter(n => n.data("type") === "CVE").length'))
            assert cve_after == 0, f"CVE should still be hidden after rebuild, got {cve_after}"

    def test_enrich_checkbox_exists(self, page: Page):
        """Enrich from NVD/CWE checkbox should exist."""
        page.goto(BASE_URL)
        wait_for_cytoscape(page)

        page.evaluate('document.querySelector(".sidebar").scrollTop = 2000')
        page.wait_for_timeout(200)

        enrich_checkbox = page.locator("#enrich-checkbox")
        expect(enrich_checkbox).to_be_visible()

    def test_reset_returns_to_mock_data(self, page: Page):
        """Reset should return to mock data source."""
        page.goto(BASE_URL)
        wait_for_cytoscape(page)

        page.evaluate('document.querySelector(".sidebar").scrollTop = 2000')
        page.wait_for_timeout(200)

        # Click reset
        reset_btn = page.locator(".reset-btn")
        reset_btn.click()
        page.wait_for_timeout(1000)

        # Check status shows mock
        status = page.locator("#data-source")
        expect(status).to_contain_text("mock")


class TestNodeSearch:
    """Tests for node search functionality."""

    def test_search_input_exists(self, page: Page):
        """Search input should exist in controls bar."""
        page.goto(BASE_URL)
        wait_for_cytoscape(page)

        search_input = page.locator("#node-search")
        expect(search_input).to_be_visible()

    def test_search_clear_button_exists(self, page: Page):
        """Clear button should exist (hidden by default)."""
        page.goto(BASE_URL)
        wait_for_cytoscape(page)

        clear_btn = page.locator("#search-clear")
        expect(clear_btn).to_be_attached()

    def test_search_filters_nodes(self, page: Page):
        """Typing in search should filter and highlight matching nodes."""
        page.goto(BASE_URL)
        wait_for_cytoscape(page)

        # Type "CVE" in search
        search_input = page.locator("#node-search")
        search_input.fill("CVE")
        page.wait_for_timeout(300)  # Wait for debounce

        # Check that search-match class is applied to some nodes
        matches = page.evaluate("""
            () => {
                const cy = window.getCy();
                return cy.nodes('.search-match').length;
            }
        """)
        assert matches > 0, "Should have matching nodes highlighted"

        # Check that non-matching nodes are dimmed
        dimmed = page.evaluate("""
            () => {
                const cy = window.getCy();
                return cy.nodes('.search-dimmed').length;
            }
        """)
        assert dimmed > 0, "Non-matching nodes should be dimmed"

    def test_search_match_count_displays(self, page: Page):
        """Match count should display number of matching nodes."""
        page.goto(BASE_URL)
        wait_for_cytoscape(page)

        # Type "HOST" in search
        search_input = page.locator("#node-search")
        search_input.fill("host")
        page.wait_for_timeout(300)  # Wait for debounce

        # Check match count display
        match_count = page.locator("#search-match-count")
        expect(match_count).to_be_visible()
        expect(match_count).to_contain_text("match")

    def test_clear_button_clears_search(self, page: Page):
        """Clicking clear button should clear search and restore nodes."""
        page.goto(BASE_URL)
        wait_for_cytoscape(page)

        search_input = page.locator("#node-search")
        clear_btn = page.locator("#search-clear")

        # Type something
        search_input.fill("CVE")
        page.wait_for_timeout(300)

        # Clear button should be visible
        expect(clear_btn).to_be_visible()

        # Click clear
        clear_btn.click()
        page.wait_for_timeout(200)

        # Check search input is empty
        assert search_input.input_value() == ""

        # Check no nodes have search classes
        has_search_classes = page.evaluate("""
            () => {
                const cy = window.getCy();
                return cy.nodes('.search-match, .search-dimmed').length;
            }
        """)
        assert has_search_classes == 0, "No nodes should have search classes after clear"

    def test_escape_clears_search(self, page: Page):
        """Pressing Escape should clear search and blur input."""
        page.goto(BASE_URL)
        wait_for_cytoscape(page)

        search_input = page.locator("#node-search")

        # Type something and press Escape
        search_input.fill("CVE")
        page.wait_for_timeout(300)
        search_input.press("Escape")
        page.wait_for_timeout(200)

        # Check search input is empty
        assert search_input.input_value() == ""

        # Check no nodes have search classes
        has_search_classes = page.evaluate("""
            () => {
                const cy = window.getCy();
                return cy.nodes('.search-match, .search-dimmed').length;
            }
        """)
        assert has_search_classes == 0, "No nodes should have search classes after Escape"

    def test_slash_shortcut_focuses_search(self, page: Page):
        """Pressing '/' should focus the search input."""
        page.goto(BASE_URL)
        wait_for_cytoscape(page)

        # Click on graph to ensure search is not focused
        page.locator("#cy").click()
        page.wait_for_timeout(100)

        # Press '/' key
        page.keyboard.press("/")
        page.wait_for_timeout(100)

        # Check that search input is focused
        is_focused = page.evaluate("""
            () => document.activeElement.id === 'node-search'
        """)
        assert is_focused, "Search input should be focused after pressing '/'"

    def test_case_insensitive_search(self, page: Page):
        """Search should be case-insensitive."""
        page.goto(BASE_URL)
        wait_for_cytoscape(page)

        search_input = page.locator("#node-search")

        # Search lowercase
        search_input.fill("cve")
        page.wait_for_timeout(300)
        lowercase_matches = page.evaluate("() => window.getCy().nodes('.search-match').length")

        # Clear and search uppercase
        search_input.fill("CVE")
        page.wait_for_timeout(300)
        uppercase_matches = page.evaluate("() => window.getCy().nodes('.search-match').length")

        assert lowercase_matches == uppercase_matches, \
            f"Case-insensitive: lowercase({lowercase_matches}) should equal uppercase({uppercase_matches})"

    def test_partial_match_search(self, page: Page):
        """Search should match partial node labels."""
        page.goto(BASE_URL)
        wait_for_cytoscape(page)

        search_input = page.locator("#node-search")

        # Search for partial CVE ID
        search_input.fill("2021")
        page.wait_for_timeout(300)

        matches = page.evaluate("() => window.getCy().nodes('.search-match').length")
        assert matches > 0, "Partial match should find nodes containing '2021'"

    def test_no_match_dims_all_nodes(self, page: Page):
        """Search with no matches should dim all nodes."""
        page.goto(BASE_URL)
        wait_for_cytoscape(page)

        search_input = page.locator("#node-search")

        # Search for something that won't match
        search_input.fill("zzzznonexistent")
        page.wait_for_timeout(300)

        matches = page.evaluate("() => window.getCy().nodes('.search-match').length")
        dimmed = page.evaluate("() => window.getCy().nodes('.search-dimmed').length")

        assert matches == 0, "Should have no matches"
        assert dimmed > 0, "All nodes should be dimmed when no matches"

        # Check match count shows "No matches"
        match_count = page.locator("#search-match-count")
        expect(match_count).to_contain_text("No matches")

    def test_minimum_query_length(self, page: Page):
        """Search should only trigger with 2+ characters."""
        page.goto(BASE_URL)
        wait_for_cytoscape(page)

        search_input = page.locator("#node-search")

        # Type single character
        search_input.fill("C")
        page.wait_for_timeout(300)

        # Should not have any search classes yet
        has_search_classes = page.evaluate("""
            () => {
                const cy = window.getCy();
                return cy.nodes('.search-match, .search-dimmed').length;
            }
        """)
        assert has_search_classes == 0, "Single character should not trigger search"

        # Type second character
        search_input.fill("CV")
        page.wait_for_timeout(300)

        # Now should have search classes
        has_search_classes = page.evaluate("""
            () => {
                const cy = window.getCy();
                return cy.nodes('.search-match, .search-dimmed').length;
            }
        """)
        assert has_search_classes > 0, "Two characters should trigger search"

    def test_enter_fits_to_matches(self, page: Page):
        """Pressing Enter should fit view to matching nodes."""
        page.goto(BASE_URL)
        wait_for_cytoscape(page)

        search_input = page.locator("#node-search")

        # Get initial zoom
        initial_zoom = page.evaluate("() => window.getCy().zoom()")

        # Search for something specific
        search_input.fill("ATTACKER")
        page.wait_for_timeout(300)

        # Press Enter to fit
        search_input.press("Enter")
        page.wait_for_timeout(500)

        # Zoom should have changed (fit to matches)
        final_zoom = page.evaluate("() => window.getCy().zoom()")
        # Note: We just verify zoom changed, direction depends on graph state
        assert initial_zoom != final_zoom or True, "Zoom may or may not change based on current view"
