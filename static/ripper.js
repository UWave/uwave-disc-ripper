function ejectOrLoad(e) {
  var slot = $(e.target).data('slot');
  var full = $(e.target).data('full');
  if(full) {
    console.log("Ejecting", slot);
  } else {
    console.log("Loading", slot);
  }
}

function makeButtons(i) {
  var buttons = $("<td>").addClass("slot_" + i).addClass("buttons");
  var eject = $("<a>").addClass("ejectOrLoad").addClass("fa").click(ejectOrLoad).data("slot", i).attr("href", "#");
  buttons.append(eject);
  return buttons;
}

function showChangerStatus(result) {
  for(var i in result.info) {
    if(result.info.hasOwnProperty(i)) {
      var slot = result.info[i];
      var row = $("tr.slot_" + i);
      if(row.length === 0) {
        row = $("<tr>").addClass("slot_" + i)
          .append($("<td>").addClass("slot_" + i).addClass("slot"))
          .append($("<td>").addClass("slot_" + i).addClass("state"))
          .append($("<td>").addClass("slot_" + i).addClass("album"))
          .append($("<td>").addClass("slot_" + i).addClass("artist"))
          .append(makeButtons(i));
        $(".slots").append(row);
      }
      $(".slot.slot_" + i).text(i);
      if(slot.hasOwnProperty("full")) {
        if(slot.full) {
          $(".state.slot_" + i).text("Full");
          $(".buttons.slot_" + i + " .ejectOrLoad").removeClass("fa-arrow-circle-down").addClass("fa-eject").data('full', true);
        } else {
          $(".state.slot_" + i).text("Empty");
          $(".buttons.slot_" + i + " .ejectOrLoad").removeClass("fa-eject").addClass("fa-arrow-circle-down").data('full', false);
        }
      }
      if(slot.hasOwnProperty("album")) {
        $(".album.slot_" + i).text(slot.album);
      }
      if(slot.hasOwnProperty("artist")) {
        $(".artist.slot_" + i).text(slot.artist);
      }
    }
  }
}

function waitFor(url, callback) {
  fetch(url).then(function(response) {
    response.json().then(function(result) {
      if(result.hasOwnProperty('updates')) {
        waitFor(result.updates, callback);
      } else if(result.state == "PENDING") {
        setTimeout(waitFor, 500, url, callback);
      } else {
        callback(result);
      }
    });
  });
}


$(document).ready(function() {
  waitFor('/changer/status', showChangerStatus);
});
