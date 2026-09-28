// =============================================================================
//  可行性验证 demo 用的"示例软件"
//  编译：csc /target:winexe /codepage:65001 /win32icon:assets\app.ico ...
//  它的作用是：让打包出来的安装包真的能装出一个可运行的程序，
//  以便验证快捷方式、安装目录、卸载项是否都正常工作。
// =============================================================================

using System;
using System.Drawing;
using System.IO;
using System.Reflection;
using System.Windows.Forms;

[assembly: AssemblyTitle("我的小工具")]
[assembly: AssemblyProduct("我的小工具")]
[assembly: AssemblyDescription("应用安装向导打包软件 —— 可行性验证示例程序")]
[assembly: AssemblyCompany("示例软件工作室")]
[assembly: AssemblyCopyright("Copyright (C) 2026 示例软件工作室")]
[assembly: AssemblyTrademark("")]
[assembly: AssemblyVersion("1.0.0.0")]
[assembly: AssemblyFileVersion("1.0.0.0")]

namespace MyApp
{
    internal static class Program
    {
        [STAThread]
        private static void Main()
        {
            Application.EnableVisualStyles();
            Application.SetCompatibleTextRenderingDefault(false);

            // 首次运行写一份用户配置，用来演示"卸载时是否保留用户数据"
            string dataDir = Path.Combine(
                Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData), "我的小工具");
            string configFile = Path.Combine(dataDir, "config.ini");
            try
            {
                Directory.CreateDirectory(dataDir);
                if (!File.Exists(configFile))
                {
                    File.WriteAllText(configFile,
                        "[general]\r\n" +
                        "first_run=" + DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss") + "\r\n" +
                        "note=这是示例程序生成的用户配置文件，" +
                        "卸载时选择「否」可以保留它。\r\n",
                        System.Text.Encoding.UTF8);
                }
            }
            catch
            {
                // 演示程序，失败也不影响启动
            }

            Application.Run(new MainForm(configFile));
        }
    }

    internal sealed class MainForm : Form
    {
        public MainForm(string configFile)
        {
            Text = "我的小工具 v1.0.0";
            ClientSize = new Size(460, 268);
            StartPosition = FormStartPosition.CenterScreen;
            FormBorderStyle = FormBorderStyle.FixedDialog;
            MaximizeBox = false;
            MinimizeBox = true;
            BackColor = Color.White;
            Icon = SystemIcons.Application;

            var title = new Label
            {
                Text = "我的小工具",
                Font = new Font("Microsoft YaHei UI", 18F, FontStyle.Bold),
                ForeColor = Color.FromArgb(26, 68, 190),
                Location = new Point(26, 22),
                AutoSize = true
            };
            Controls.Add(title);

            var subtitle = new Label
            {
                Text = "应用安装向导打包软件 —— 可行性验证示例",
                Font = new Font("Microsoft YaHei UI", 9F),
                ForeColor = Color.FromArgb(130, 140, 160),
                Location = new Point(29, 62),
                AutoSize = true
            };
            Controls.Add(subtitle);

            var body = new Label
            {
                Text =
                    "安装成功，说明打包链路完全正常。\r\n\r\n" +
                    "程序目录：\r\n" + Application.StartupPath + "\r\n\r\n" +
                    "配置文件：\r\n" + configFile,
                Font = new Font("Microsoft YaHei UI", 9F),
                ForeColor = Color.FromArgb(64, 64, 64),
                Location = new Point(29, 92),
                Size = new Size(400, 130)
            };
            Controls.Add(body);

            var ok = new Button
            {
                Text = "知道了",
                Location = new Point(346, 222),
                Size = new Size(88, 30),
                FlatStyle = FlatStyle.System
            };
            ok.Click += delegate { Close(); };
            Controls.Add(ok);
            AcceptButton = ok;
        }
    }
}
