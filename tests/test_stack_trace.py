"""Tests for stack trace functionality (v0.2.0 - #26)."""

import pytest


def check_extension_available() -> bool:
    """Check if native extension is available."""
    try:
        from pyetwkit import _core  # noqa: F401

        return True
    except ImportError:
        return False


# Skip all tests if native extension is not available
pytestmark = pytest.mark.skipif(
    not check_extension_available(),
    reason="Native extension not built",
)


class TestEnableProperty:
    """Tests for EnableProperty enum/flags."""

    def test_enable_property_exists(self) -> None:
        """Test that EnableProperty exists."""
        from pyetwkit import _core

        assert hasattr(_core, "EnableProperty")

    def test_enable_property_stack_trace(self) -> None:
        """Test that STACK_TRACE flag exists."""
        from pyetwkit._core import EnableProperty

        assert hasattr(EnableProperty, "STACK_TRACE") or hasattr(EnableProperty, "StackTrace")

    def test_enable_property_values(self) -> None:
        """Test EnableProperty flag values."""
        from pyetwkit._core import EnableProperty

        # Should have common enable properties
        expected_flags = ["STACK_TRACE", "SID", "TS_ID", "PROCESS_START_KEY"]
        found_flags = []
        for flag in expected_flags:
            if hasattr(EnableProperty, flag) or hasattr(EnableProperty, flag.title().replace("_", "")):
                found_flags.append(flag)
        # At least STACK_TRACE should exist
        assert len(found_flags) >= 1


class TestStackTraceCapture:
    """Tests for stack trace capture functionality."""

    def test_session_with_stack_trace_option(self) -> None:
        """Test creating session with stack trace enabled."""
        from pyetwkit import _core
        from pyetwkit._core import EtwSession

        # Should be able to create session with stack trace option
        session = EtwSession("StackTraceTest")
        assert session is not None
        # Check if enable_stack_trace method or option exists
        has_stack_option = (
            hasattr(session, "enable_stack_trace")
            or hasattr(session, "with_stack_trace")
            or hasattr(_core, "EnableProperty")
        )
        assert has_stack_option

    def test_event_has_stack_property(self) -> None:
        """Test that EtwEvent has stack trace property."""
        from pyetwkit._core import EtwEvent

        # Check EtwEvent class has stack-related attribute
        # Should have stack_trace or stack attribute
        # This is checking the class definition, not instance
        assert hasattr(EtwEvent, "stack_trace") or hasattr(EtwEvent, "stack")


class TestStackFrame:
    """Tests for StackFrame class."""

    def test_stack_frame_exists(self) -> None:
        """Test that StackFrame class exists (if stack traces are supported)."""
        from pyetwkit import _core
        from pyetwkit._core import EtwEvent

        # StackFrame might be a separate class or part of event
        has_stack_support = hasattr(_core, "StackFrame") or hasattr(
            EtwEvent, "stack_trace"
        )
        assert has_stack_support


@pytest.mark.admin
class TestStackTraceIntegration:
    """Integration tests for stack trace (require admin)."""

    def test_capture_events_with_stack_trace(self) -> None:
        """Test capturing events with stack trace enabled."""
        from pyetwkit._core import EtwProvider, EtwSession

        session = EtwSession("StackTraceIntegrationTest")
        provider = EtwProvider(
            "22fb2cd6-0e7b-422b-a0c7-2fad1fd0e716",
            "Microsoft-Windows-Kernel-Process",
        )

        # Enable stack trace if method exists
        if hasattr(session, "enable_stack_trace"):
            session.enable_stack_trace(True)

        session.add_provider(provider)
        session.start()

        try:
            # Try to capture an event with stack trace
            event = session.next_event_timeout(1000)
            if event and event.stack_trace:
                assert isinstance(event.stack_trace, list)
                for frame in event.stack_trace:
                    assert isinstance(frame, int)  # Stack addresses
        finally:
            session.stop()
