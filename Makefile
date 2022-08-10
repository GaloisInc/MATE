OUTPUT:=mate-code-drop.tar

.PHONY: code-drop
code-drop: sync mate-code-drop.tar.bz2

.PHONY: clean
clean:
	rm -f mate-code-drop.tar.bz2

.PHONY: sync
sync:
	git submodule sync --recursive
	git submodule update --init --recursive submodules/integration_framework
	git submodule update --init --recursive submodules/message_set_coordination
	git submodule update --init --recursive submodules/manticore

mate-code-drop.tar.bz2:
	./ci/git_archive.sh $(OUTPUT)
