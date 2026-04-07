cask "kprompter" do
  version :latest
  sha256 :no_check

  url "https://github.com/ktorres0109/kprompter/releases/latest/download/KPrompter.dmg"
  name "KPrompter"
  desc "Turn rough text into AI-ready prompts instantly"
  homepage "https://github.com/ktorres0109/kprompter"

  app "KPrompter.app"

  postflight do
    system_command "xattr",
                   args: ["-cr", "#{appdir}/KPrompter.app"],
                   sudo: false,
                   must_succeed: false
  end
end
