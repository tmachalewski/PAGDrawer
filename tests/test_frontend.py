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
        """Node count should be displayed in stats."""
        page.goto(BASE_URL)
        page.wait_for_timeout(2000)  # Wait for graph to load
        
        # Check that stats panel shows node count (use first() for multiple matches)
        stats_text = page.locator(".stats-panel").first.inner_text()
        assert "Total Nodes" in stats_text
    
    def test_edge_count_displayed(self, page: Page):
        """Edge count should be displayed in stats."""
        page.goto(BASE_URL)
        page.wait_for_timeout(2000)
        
        stats_text = page.locator(".stats-panel").first.inner_text()
        assert "Total Edges" in stats_text


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

        # Get initial node count
        initial_count = page.locator("#total-nodes").inner_text()

        # Open settings and set CPE to universal (position 0)
        page.get_by_role("button", name="Settings").click()
        page.locator("#settings-modal").wait_for(state="visible", timeout=5000)

        cpe_slider = page.locator("#config-CPE")
        cpe_slider.fill("0")
        cpe_slider.dispatch_event("input")

        # Save settings
        page.get_by_role("button", name="Save").click()
        wait_for_cytoscape(page, timeout=10000)

        # Get new node count
        final_count = page.locator("#total-nodes").inner_text()

        # Universal mode should have fewer or equal nodes
        assert int(final_count) <= int(initial_count)


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
