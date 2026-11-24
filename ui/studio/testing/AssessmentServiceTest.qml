import QtQuick
import QtTest
import ".." as Studio

Item {
    property string screenshotFolder: ""

    QtObject {
        id: backend
        property bool busy: false
        property var pending: []
        property var notices: []
        function request(arguments, callback) {
            pending = pending.concat([{arguments: arguments, callback: callback}]);
        }
        function notify(message, failure) { notices = notices.concat([{message: message, failure: failure}]); }
    }
    Studio.CheckworkService { id: service; api: backend }

    TestCase {
        name: "AssessmentResponses"
        when: true

        function init() {
            service.openFor("fixture");
            backend.pending[backend.pending.length - 1].callback([], "");
            backend.pending = [];
            backend.notices = [];
        }
        function test_refresh_keeps_newer_user_selection() {
            service.report = {id: "removed"};
            service.reports = [{id: "removed"}, {id: "chosen"}, {id: "latest"}];
            service.refresh();
            service.selectReport("chosen");
            backend.pending[0].callback([{id: "latest"}, {id: "chosen"}], "");
            compare(backend.pending.length, 2, "Refresh must not queue a selection over the user's choice");
            verify(service.loading, "Selected report is still loading");
            backend.pending[1].callback({id: "chosen"}, "");
            compare(service.report.id, "chosen");
            verify(!service.loading);
        }
        function test_latest_selection_wins() {
            service.selectReport("first");
            service.selectReport("second");
            backend.pending[0].callback({id: "first"}, "");
            compare(service.report, null);
            verify(service.loading);
            backend.pending[1].callback({id: "second"}, "");
            compare(service.report.id, "second");
        }
        function test_failed_check_releases_superseded_loading_data() {
            return [{tag: "history", history: true}, {tag: "selection", history: false}];
        }
        function test_failed_check_releases_superseded_loading(data) {
            if (data.history)
                service.refresh();
            else
                service.selectReport("old");
            verify(service.loading);
            service.check();
            backend.pending[0].callback(data.history ? [{id: "old"}] : {id: "old"}, "");
            backend.pending[1].callback(null, "Checkwork failed");
            verify(!service.checking);
            verify(!service.loading, "No request remains; refresh must become available again");
            compare(service.error, "Checkwork failed");
        }
        function test_successful_check_keeps_new_report() {
            service.check();
            verify(service.checking);
            backend.pending[0].callback({id: "new"}, "");
            verify(!service.checking);
            compare(service.report.id, "new");
            backend.pending[1].callback([{id: "new"}], "");
            verify(!service.loading);
            compare(service.report.id, "new");
        }
        function test_previous_session_response_is_ignored() {
            service.selectReport("old");
            service.openFor("other");
            backend.pending[0].callback({id: "old"}, "");
            compare(service.report, null);
            backend.pending[1].callback([], "");
            verify(!service.loading);
        }
        function test_invalid_export_response_reports_failure_data() {
            return [{tag: "null", result: null}, {tag: "empty", result: {}}, {tag: "wrong-type", result: {destination: 42}}];
        }
        function test_invalid_export_response_reports_failure(data) {
            service.exportReport("report", "/tmp/fixture.zip");
            backend.pending[0].callback(data.result, "");
            compare(backend.notices.length, 1);
            verify(backend.notices[0].failure);
        }
        function test_export_success_and_transport_failure() {
            service.exportReport("report", "/tmp/fixture.zip");
            backend.pending[0].callback({destination: "/tmp/fixture.zip"}, "");
            compare(backend.notices.length, 1);
            verify(!backend.notices[0].failure);
            service.exportReport("report", "/tmp/fixture.zip");
            backend.pending[1].callback(null, "transport error");
            compare(backend.notices.length, 1);
        }
    }
}
