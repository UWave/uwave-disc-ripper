function ejectOrLoad(e) {
  console.log(e);
}

function makeButtons(i) {
  var buttons = $("<td>").addClass("slot_" + i).addClass("buttons");
  var eject = $("<a>").addClass("ejectOrLoad").addClass("fa").click(ejectOrLoad).data("slot", i).attr("href", "javascript: void(0);");
  buttons.append(eject);
  return buttons;
}

function updateList() {
  fetch('/changer_status').then(function(response) {
    response.json().then(function(slots) {
      for(var i in slots) {
        if(slots.hasOwnProperty(i)) {
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
          if(slots[i].hasOwnProperty("full")) {
            if(slots[i].full) {
              $(".state.slot_" + i).text("Full");
              $(".buttons.slot_" + i + " .ejectOrLoad").removeClass("fa-arrow-circle-down").addClass("fa-eject");
            } else {
              $(".state.slot_" + i).text("Empty");
              $(".buttons.slot_" + i + " .ejectOrLoad").removeClass("fa-eject").addClass("fa-arrow-circle-down");
            }
          }
          if(slots[i].hasOwnProperty("album")) {
            $(".album.slot_" + i).text(slots[i].album);
          }
          if(slots[i].hasOwnProperty("artist")) {
            $(".artist.slot_" + i).text(slots[i].artist);
          }
        }
      }
    });
  });
}

$(document).ready(updateList);
